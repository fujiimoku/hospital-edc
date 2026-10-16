import io
import zipfile
from urllib.parse import unquote
from pathlib import Path
import importlib.util

import pytest
from PIL import Image
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.config import settings
from app.models.patient_image import PatientImage
from app.models.audit_log import AuditLog
from app.study import GROUP_SUBGROUPS, STUDY_GROUPS
from app.services.export import build_patient_table
from tests.conftest import auth_header
from tests.test_crf_alignment import create_patient, create_visit


@pytest.fixture(autouse=True)
def image_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))


def picture(kind='PNG'):
    data = io.BytesIO()
    Image.new('RGB', (16, 20), 'white').save(data, kind)
    return data.getvalue()


def upload(client, token, pid, data=None, name='photo.png'):
    return client.post(f'/api/patients/{pid}/images', headers=auth_header(token),
                       files={'file': (name, picture() if data is None else data, 'image/png')})


def test_images_roundtrip_archive_names_audit_and_private_storage(client, admin_token, db):
    patient = create_patient(client, admin_token, full_name='测试患者', study_group='integrated_weekly', study_subgroup='icodec')
    pid = patient['id']
    responses = [upload(client, admin_token, pid, name='../../escape.png') for _ in range(2)]
    assert all(r.status_code == 201 for r in responses)
    ids = [r.json()['id'] for r in responses]
    listing = client.get(f'/api/patients/{pid}/images', headers=auth_header(admin_token)).json()
    names = [i['filename'] for i in listing['items']]
    assert len(set(names)) == 2
    assert all(n.startswith('A组-测试患者-' + patient['patient_code']) for n in names)
    downloaded = client.get(f'/api/patients/{pid}/images/{ids[0]}/download', headers=auth_header(admin_token))
    assert downloaded.content == picture()
    assert names[0] in unquote(downloaded.headers['content-disposition'])
    assert downloaded.headers['cache-control'] == 'no-store'
    archive = client.get(f'/api/patients/{pid}/images/archive', headers=auth_header(admin_token))
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        assert zipped.namelist() == names
        assert all(zipped.read(n) == picture() for n in names)
    events = db.query(AuditLog).filter(AuditLog.table_name == 'patient_images', AuditLog.record_id.in_(ids)).all()
    assert {e.action for e in events} == {'upload', 'download', 'download_archive'}
    assert all('测试患者' not in (e.new_value or '') for e in events)
    rows = db.query(PatientImage).filter(PatientImage.id.in_(ids)).all()
    assert all('escape' not in r.storage_key and '测试患者' not in r.storage_key for r in rows)
    assert client.get('/uploads/patient_images/' + rows[0].storage_key).status_code == 404


def test_access_cross_center_cross_patient_qc_and_anonymous(client, researcher1_token, researcher2_token, qc1_token):
    p1 = create_patient(client, researcher1_token)
    p2 = create_patient(client, researcher2_token)
    image_id = upload(client, researcher1_token, p1['id']).json()['id']
    for token in [researcher2_token, qc1_token]:
        for suffix in ['', '/archive', f'/{image_id}/download']:
            assert client.get(f"/api/patients/{p1['id']}/images{suffix}", headers=auth_header(token)).status_code == 403
        assert upload(client, token, p1['id']).status_code == 403
    assert client.get(f"/api/patients/{p2['id']}/images/{image_id}/download", headers=auth_header(researcher2_token)).status_code == 404
    assert client.get(f"/api/patients/{p1['id']}/images").status_code == 401
    assert client.post(f"/api/patients/{p1['id']}/images", files={'file': ('a.png', picture())}).status_code == 401


@pytest.mark.parametrize('data', [b'', b'<svg onload="alert(1)"></svg>', b'%PDF-1.4', b'\x89PNG\r\n\x1a\ninvalid'])
def test_reject_non_images(client, admin_token, data):
    patient = create_patient(client, admin_token)
    assert upload(client, admin_token, patient['id'], data).status_code == 422
    assert not list(Path(settings.UPLOAD_DIR).rglob('*'))


def test_size_limit_and_safe_filename(client, admin_token, monkeypatch):
    patient = create_patient(client, admin_token, full_name='../../坏名\r\n"', study_group='usual_daily')
    response = upload(client, admin_token, patient['id'], picture('JPEG'), 'anything.exe')
    assert response.status_code == 201  # Real image type determines stored extension.
    assert response.json()['filename'].startswith('D组-')
    assert response.json()['filename'].endswith('.jpg')
    assert not any(c in response.json()['filename'] for c in ['/', '\\', '\r', '\n', '"'])
    monkeypatch.setattr('app.routers.patient_images.MAX_BYTES', 3)
    assert upload(client, admin_token, patient['id']).status_code == 413


def test_storage_failure_rolls_back_metadata(client, admin_token, monkeypatch, db):
    patient = create_patient(client, admin_token)
    from sqlalchemy.orm import Session
    def fail(*args, **kwargs):
        raise RuntimeError('simulated database failure')
    with monkeypatch.context() as patch:
        patch.setattr(Session, 'commit', fail)
        with pytest.raises(RuntimeError, match='simulated'):
            upload(client, admin_token, patient['id'])
    assert db.query(PatientImage).filter_by(patient_id=patient['id']).count() == 0
    assert not list((Path(settings.UPLOAD_DIR) / 'patient_images').iterdir())


def test_subgroups_all_twelve_combinations_validation_lock_export_and_counts(client, admin_token, db):
    from app.models.patient import Patient
    from datetime import datetime
    patients = []
    for group, options in GROUP_SUBGROUPS.items():
        for option in options:
            p = create_patient(client, admin_token, study_group=group, study_subgroup=option)
            assert p['study_subgroup'] == option
            patients.append(p)
    for p in patients:
        db.get(Patient, p['id']).created_at = datetime(2034, 1, 2, 12)
    db.commit()
    p = patients[0]
    header = auth_header(admin_token)
    assert client.put(f"/api/patients/{p['id']}", headers=header, json={'study_group': 'integrated_daily'}).status_code == 422
    assert client.post('/api/patients/', headers=header, json={'name_initials':'BAD', 'gender':'male','study_subgroup':'icodec'}).status_code == 422
    assert client.put(f"/api/patients/{p['id']}", headers=header, json={'study_subgroup':'unknown'}).status_code == 422
    visit = create_visit(client, admin_token, p['id'])
    assert client.post(f'/api/visits/{visit}/submit', headers=header).status_code == 200
    assert client.put(f"/api/patients/{p['id']}", headers=header, json={'study_subgroup':'semaglutide'}).status_code == 400
    # Source pictures are append-only patient attachments, independent of signed CRF values.
    assert upload(client, admin_token, p['id']).status_code == 201
    exported = build_patient_table(db, None)
    assert exported.loc[exported.patient_code == p['patient_code'], 'study_subgroup'].iloc[0] == 'icodec'
    report = client.get('/api/reports/weekly-entry?week=2034-01-02', headers=header).json()
    assert report['total'] == 12
    row = next(r for r in report['items'] if r['center_id'] == p['center_id'])
    for group, options in GROUP_SUBGROUPS.items():
        assert row['groups'][group] == 3
        assert [row['subgroups'][group][k] for k in options] == [1, 1, 1]
    assert STUDY_GROUPS['usual_daily'] == 'D组：常规诊疗+周制剂'


def test_additive_migration_is_repeatable_and_preserves_old_rows():
    file = Path(__file__).parents[1] / 'alembic/versions/20261014_patient_images.py'
    spec = importlib.util.spec_from_file_location('images_migration', file)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE patients (id INTEGER PRIMARY KEY, study_group VARCHAR(32))'))
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        conn.execute(text("INSERT INTO patients VALUES (1, 'usual_daily')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade(); migration.upgrade()
        assert conn.execute(text('SELECT id, study_group, study_subgroup FROM patients')).one() == (1, 'usual_daily', None)
        assert 'patient_images' in inspect(conn).get_table_names()

def test_visit_cost_images_scope_draft_and_empty_cost_submission(client, admin_token):
    p = create_patient(client, admin_token)
    other = create_patient(client, admin_token)
    v = create_visit(client, admin_token, p['id'])
    v2 = create_visit(client, admin_token, p['id'], 'W26')
    headers = auth_header(admin_token)
    url = f"/api/patients/{p['id']}/images?visit_id={v}"
    r = client.post(url, headers=headers, files={'file': ('cost.png', picture(), 'image/png')})
    assert r.status_code == 201, r.text
    assert r.json()['visit_id'] == v
    assert len(client.get(url, headers=headers).json()['items']) == 1
    assert client.get(f"/api/patients/{p['id']}/images?visit_id={v2}", headers=headers).json()['items'] == []
    assert client.post(f"/api/patients/{other['id']}/images?visit_id={v}", headers=headers,
                       files={'file': ('cost.png', picture(), 'image/png')}).status_code == 404
    assert client.post(f"/api/visits/{v}/cost-indicators", headers=headers,
                       json={'crf_version': 1, 'drug_cost': None, 'lab_cost': None, 'service_cost': None, 'supply_cost': None, 'other_cost': None}).status_code == 200
    assert client.post(f"/api/visits/{v}/submit", headers=headers).status_code == 200
    assert client.post(url, headers=headers, files={'file': ('cost.png', picture(), 'image/png')}).status_code == 400
    assert len(client.get(url, headers=headers).json()['items']) == 1


def test_age_correction_short_reason_and_audit(client, admin_token, db):
    p = create_patient(client, admin_token, age=50)
    v = create_visit(client, admin_token, p['id'])
    headers = auth_header(admin_token)
    url = f"/api/patients/{p['id']}"
    assert client.put(url, headers=headers, json={'age': 51}).status_code == 200
    assert client.put(url, headers=headers, json={'age': -1}).status_code == 422
    assert client.post(f"/api/visits/{v}/submit", headers=headers).status_code == 200
    assert client.put(url, headers=headers, json={'age': 52}).status_code == 400
    assert client.post(f"/api/visits/{v}/reopen", headers=headers, json={'reason': '年龄录入错误'}).status_code == 200
    assert client.put(url, headers=headers, json={'age': 52}).json()['age'] == 52
    assert db.query(AuditLog).filter_by(table_name='patients', record_id=p['id'], field_name='age').count() >= 2

@pytest.mark.parametrize('already_has_column', [False, True])
def test_visit_photo_migration_preserves_existing_archive(already_has_column):
    file = Path(__file__).parents[1] / 'alembic/versions/20261016_trial_feedback.py'
    spec = importlib.util.spec_from_file_location('feedback_migration', file)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE visits (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE patient_images (id INTEGER PRIMARY KEY, storage_key VARCHAR(64))'))
        if already_has_column:
            conn.execute(text('ALTER TABLE patient_images ADD COLUMN visit_id INTEGER'))
        conn.execute(text("INSERT INTO patient_images (id, storage_key) VALUES (1, 'existing.png')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            migration.upgrade()
        assert conn.execute(text('SELECT id, storage_key, visit_id FROM patient_images')).one() == (1, 'existing.png', None)
        assert inspect(conn).get_foreign_keys('patient_images')[0]['referred_table'] == 'visits'
