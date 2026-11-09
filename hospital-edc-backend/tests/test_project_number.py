import csv
import importlib.util
import io
import zipfile
from pathlib import Path

import openpyxl
from sqlalchemy import create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.conftest import auth_header
from tests.test_crf_alignment import create_patient, create_visit


def test_project_number_roundtrip_and_permissions(client, researcher1_token, researcher2_token):
    h = auth_header(researcher1_token)
    patient = create_patient(client, researcher1_token, edc_project_number='  0007-A  ')
    url = f"/api/patients/{patient['id']}"
    assert patient['edc_project_number'] == '0007-A'
    assert client.get(url, headers=h).json()['edc_project_number'] == '0007-A'
    assert client.put(url, headers=auth_header(researcher2_token), json={'edc_project_number': 'X'}).status_code == 403
    assert client.put(url, headers=h, json={'edc_project_number': 'x' * 51}).status_code == 422
    assert client.put(url, headers=h, json={'edc_project_number': ' '}).json()['edc_project_number'] is None


def test_project_number_export_order_xlsx_csv(client, researcher1_token, researcher2_token):
    patients = [create_patient(client, researcher1_token, edc_project_number=n)
                for n in ('PN10', None, 'PN2', 'PN2')]
    for p in patients:
        create_visit(client, researcher1_token, p['id'])
    foreign = create_patient(client, researcher2_token, edc_project_number='PN0')
    expected = [patients[i]['patient_code'] for i in (2, 3, 0, 1)]
    h = auth_header(researcher1_token)
    for fmt in ('xlsx', 'csv'):
        r = client.get(f'/api/export/?format={fmt}&sort=edc_project_number', headers=h)
        assert r.status_code == 200, r.text
        if fmt == 'xlsx':
            wb = openpyxl.load_workbook(io.BytesIO(r.content))
            sheets = {}
            for name in ('患者主表', '访视宽表'):
                rows = list(wb[name].values)
                sheets[name] = [dict(zip(rows[0], row)) for row in rows[1:]]
        else:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                sheets = {name: list(csv.DictReader(io.StringIO(z.read(name + '.csv').decode('utf-8-sig'))))
                          for name in ('患者主表', '访视宽表')}
        for rows in sheets.values():
            codes = [row['patient_code'] for row in rows]
            assert foreign['patient_code'] not in codes
            assert [c for c in codes if c in expected] == expected
            assert all('edc_project_number' in row for row in rows)
    assert client.get('/api/export/?sort=bad', headers=h).status_code == 422


def test_project_number_migration_preserves_old_data_and_restarts():
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20261109_project_number.py'
    spec = importlib.util.spec_from_file_location('project_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE patients (id INTEGER PRIMARY KEY, patient_code VARCHAR(20))'))
        conn.execute(text("INSERT INTO patients VALUES (1, 'TEST-1')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            conn.execute(text("UPDATE patients SET edc_project_number='0001' WHERE id=1"))
            migration.upgrade()
        assert conn.execute(text('SELECT * FROM patients')).all() == [(1, 'TEST-1', '0001')]
