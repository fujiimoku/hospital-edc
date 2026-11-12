import importlib.util
from pathlib import Path
from app.models.patient import Patient
from app.models.visit import Visit
from tests.test_crf_alignment import create_patient, create_visit
from tests.test_patient_images import upload, image_storage


def test_quick_upload_after_approval(client, admin_token, db, image_storage):
    p = create_patient(client, admin_token)
    vid = create_visit(client, admin_token, p['id'])
    v = db.get(Visit, vid)
    v.status = 'locked'
    db.commit()
    response = upload(client, admin_token, p['id'])
    assert response.status_code in (200, 201), response.text
    assert response.json()['visit_id'] is None
    db.refresh(v)
    assert v.status == 'locked'


def test_requested_deletion_scoped_and_name_checked(client, admin_token, db, monkeypatch):
    p = create_patient(client, admin_token, full_name='删除测试')
    other = create_patient(client, admin_token)
    vid = create_visit(client, admin_token, p['id'])
    path = Path(__file__).resolve().parents[1] / 'scripts/delete_requested_patient.py'
    spec = importlib.util.spec_from_file_location('delete_requested', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'engine', db.get_bind())
    args = ['delete_requested', '--code', p['patient_code'], '--name', '删除测试']
    monkeypatch.setattr(module.sys, 'argv', args)
    module.main()
    assert db.get(Patient, p['id'])
    monkeypatch.setattr(module.sys, 'argv', args + ['--execute'])
    module.main()
    db.expire_all()
    assert db.get(Patient, p['id']) is None
    assert db.get(Visit, vid) is None
    assert db.get(Patient, other['id']) is not None
