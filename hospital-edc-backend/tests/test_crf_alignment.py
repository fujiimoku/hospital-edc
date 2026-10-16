from datetime import date, datetime
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.conftest import auth_header
from app.models.patient import Patient
from app.models.audit_log import AuditLog
from app.models.visit import Visit
from app.study import STUDY_GROUPS
from app.services.export import build_patient_table, build_visit_wide_table
from app.services.reminder import _next_expected_visit


def create_patient(client, token, **fields):
    response = client.post('/api/patients/', headers=auth_header(token), json={
        'name_initials': 'CRF', 'gender': 'female', **fields})
    assert response.status_code == 200, response.text
    return response.json()


def create_visit(client, token, pid, kind='W12', when='2026-10-12'):
    response = client.post(f'/api/patients/{pid}/visits', headers=auth_header(token),
                           json={'visit_type': kind, 'visit_date': when})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_groups_roundtrip_validation_and_audit(client, admin_token, db):
    for group in STUDY_GROUPS:
        patient = create_patient(client, admin_token, study_group=group, smoking_history=2)
        assert patient['study_group'] == group
        assert patient['smoking_history'] == 2
        assert db.query(AuditLog).filter_by(table_name='patients', record_id=patient['id'],
                                            field_name='study_group', new_value=group).count() == 1
    response = client.put(f"/api/patients/{patient['id']}", headers=auth_header(admin_token),
                          json={'study_group': 'invented_group'})
    assert response.status_code == 422
    assert client.get(f"/api/patients/{patient['id']}", headers=auth_header(admin_token)).json()['study_group'] == group


def test_week_boundary_counts_people_not_visits_or_enrollment(client, admin_token, researcher2_token, db, seed):
    dates = ['2030-01-07 00:00:00', '2030-01-13 23:59:59', '2030-01-06 23:59:59', '2030-01-14 00:00:00']
    for i, timestamp in enumerate(dates):
        p = create_patient(client, admin_token, study_group='usual_weekly', enrollment_date='2020-01-01')
        db.query(Patient).filter_by(id=p['id']).update({'created_at': datetime.fromisoformat(timestamp)})
    unknown = create_patient(client, researcher2_token)
    db.query(Patient).filter_by(id=unknown['id']).update({'created_at': datetime(2030, 1, 8)})
    db.commit()
    create_visit(client, researcher2_token, unknown['id'], 'baseline')
    create_visit(client, researcher2_token, unknown['id'], 'W12')
    response = client.get('/api/reports/weekly-entry?week=2030-01-09', headers=auth_header(researcher2_token))
    assert response.status_code == 200
    data = response.json()
    assert data['week_start'] == '2030-01-07' and data['week_end'] == '2030-01-13'
    assert data['total'] == 3
    rows = {c['center_id']: c for c in data['items']}
    assert rows[seed['c1']]['groups']['usual_weekly'] == 2
    assert rows[seed['c2']]['unassigned'] == 1
    assert all(set(row['groups']) == set(STUDY_GROUPS) for row in data['items'])
    assert 'patient_code' not in response.text and 'name_initials' not in response.text
    assert client.get('/api/reports/weekly-entry').status_code == 401


def test_main_and_interim_visit_schedule(client, admin_token):
    p = create_patient(client, admin_token, enrollment_date='2026-01-01')
    for kind in ('baseline', 'W12', 'W26'):
        create_visit(client, admin_token, p['id'], kind)
    create_visit(client, admin_token, p['id'], 'interim', '2026-02-01')
    create_visit(client, admin_token, p['id'], 'interim', '2026-03-01')
    for kind in ('W12', 'interim'):
        response = client.post('/api/visits/', headers=auth_header(admin_token), json={
            'patient_id': p['id'], 'visit_type': kind, 'visit_date': '2026-02-01'})
        assert response.status_code == 400
    assert client.post('/api/visits/', headers=auth_header(admin_token), json={
        'patient_id': p['id'], 'visit_type': 'W99', 'visit_date': '2026-02-01'}).status_code == 422
    model = Patient(enrollment_date=date(2026, 1, 1))
    assert _next_expected_visit(model, {'baseline'}) == ('W12', date(2026, 3, 26))
    assert _next_expected_visit(model, {'baseline', 'W12'}) == ('W26', date(2026, 7, 2))
    assert _next_expected_visit(model, {'baseline', 'M6'}) == (None, None)


def test_new_fields_roundtrip_export_audit_and_permissions(client, admin_token, researcher2_token, qc1_token, db):
    patient = create_patient(client, admin_token, study_group='integrated_daily', smoking_status=3, smoking_history=2)
    vid = create_visit(client, admin_token, patient['id'])
    header = auth_header(admin_token)
    forms = {
        'comorbidity': {'hypertension': 1, 'hypertension_date': '2020/03', 'hypertension_cause': '测试病因',
                        'ckd_cause': '待确认', 'angina': 1, 'mi': 0, 'dr': 1, 'dr_macular': True},
        'lab-results': {'egfr': 90.5, 'ua': 350.2},
        'cost-indicators': {'drug_cost': 100.01, 'lab_cost': 20, 'service_cost': 5,
                            'supply_cost': 8.09, 'other_cost': None, 'crf_version': 1},
        'followup-safety': {'hypoglycemia': 2, 'nocturnal': True, 'gastrointestinal': True, 'other': '测试'},
        'medications': {'medications': [{'drug_name': '测试药品', 'treatment_type': '糖尿病', 'dose': '1单位',
                          'route': '皮下注射', 'frequency': '每周一次', 'start_date': '2026-01-01', 'is_ongoing': False}]},
        'questionnaire': {'questionnaire_type': 'dtsq', 'q1': 2, 'q8': 4, 'q9': 5,
                           'dtsq_open_text': '测试建议', 'crf_version': 1},
    }
    for endpoint, payload in forms.items():
        response = client.post(f'/api/visits/{vid}/{endpoint}', headers=header, json=payload)
        assert response.status_code == 200, response.text
    data = client.get(f'/api/visits/{vid}/all-forms', headers=header).json()
    assert data['comorbidity']['hypertension_cause'] == '测试病因'
    assert data['medications'][0]['route'] == '皮下注射'
    assert data['cost_indicators']['supply_cost'] == 8.09
    assert data['followup_safety']['nocturnal'] is True
    assert db.query(AuditLog).filter_by(table_name='followup_safety', field_name='hypoglycemia').count() >= 1
    wide = build_visit_wide_table(db, None)
    row = wide.loc[wide.patient_code == patient['patient_code']].iloc[0]
    assert row.dtsq_q9 == 4 and row.dtsq_q10 == 5 and row.dtsq_q8_text == '测试建议'
    assert row.safety_hypoglycemia == 2 and row.cost_crf_version == 1
    patients = build_patient_table(db, None)
    assert patients.loc[patients.patient_code == patient['patient_code']].iloc[0].study_group == 'integrated_daily'
    assert client.post(f'/api/visits/{vid}/followup-safety', headers=auth_header(researcher2_token), json={}).status_code == 403
    assert client.post(f'/api/visits/{vid}/followup-safety', headers=auth_header(qc1_token), json={}).status_code == 403
    db.query(Visit).filter_by(id=vid).update({'status': 'signed'})
    db.commit()
    assert client.post(f'/api/visits/{vid}/followup-safety', headers=header, json={}).status_code == 400
    assert client.put(f"/api/patients/{patient['id']}", headers=header,
                      json={'study_group': 'usual_daily'}).status_code == 400


@pytest.mark.parametrize('endpoint,payload', [
    ('followup-safety', {'hypoglycemia': 1, 'severe': True}),
    ('followup-safety', {'hypoglycemia': 3}),
    ('comorbidity', {'hypertension': 2}),
    ('cost-indicators', {'drug_cost': -1}),
    ('questionnaire', {'questionnaire_type': 'dtsq', 'q1': 6}),
    ('questionnaire', {'questionnaire_type': 'eq5d', 'eq_vas_score': 101}),
])
def test_invalid_crf_values_rejected(client, admin_token, endpoint, payload):
    p = create_patient(client, admin_token)
    vid = create_visit(client, admin_token, p['id'])
    assert client.post(f'/api/visits/{vid}/{endpoint}', headers=auth_header(admin_token), json=payload).status_code == 422


def test_additive_migration_is_repeatable_preserves_old_data():
    spec = importlib.util.spec_from_file_location('crf', Path(__file__).parents[1] / 'alembic/versions/20261012_crf_alignment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        for sql in [
            'CREATE TABLE patients (id INTEGER PRIMARY KEY, smoking_status INTEGER)',
            'CREATE TABLE visits (id INTEGER PRIMARY KEY, visit_type VARCHAR(20))',
            'CREATE TABLE comorbidities (id INTEGER PRIMARY KEY)',
            'CREATE TABLE cost_indicators (id INTEGER PRIMARY KEY, service_cost FLOAT)',
            'CREATE TABLE questionnaires (id INTEGER PRIMARY KEY, q8 INTEGER)',
            'INSERT INTO patients VALUES (1,3)', 'INSERT INTO visits VALUES (1,"M6")',
            'INSERT INTO cost_indicators VALUES (1,888.25)', 'INSERT INTO questionnaires VALUES (1,4)',
        ]:
            conn.execute(text(sql))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            module.upgrade()
        assert conn.execute(text('SELECT smoking_status, study_group FROM patients')).one() == (3, None)
        assert conn.execute(text('SELECT visit_type FROM visits')).scalar() == 'M6'
        assert conn.execute(text('SELECT service_cost, crf_version FROM cost_indicators')).one() == (888.25, None)
        assert conn.execute(text('SELECT q8, crf_version FROM questionnaires')).one() == (4, None)
        assert 'followup_safety' in inspect(conn).get_table_names()


def test_safety_audit_uses_patient_center_and_draft_delete_has_no_orphan(client, admin_token, researcher2_token, db, seed):
    from app.models.forms import FollowupSafety
    patient = create_patient(client, researcher2_token)
    vid = create_visit(client, admin_token, patient['id'])
    response = client.post(f'/api/visits/{vid}/followup-safety', headers=auth_header(admin_token),
                           json={'hypoglycemia': 1})
    assert response.status_code == 200
    record = db.query(FollowupSafety).filter_by(visit_id=vid).one()
    audit = db.query(AuditLog).filter_by(table_name='followup_safety', record_id=record.id,
                                       field_name='hypoglycemia').one()
    assert audit.center_id == seed['c2']
    assert client.delete(f'/api/visits/{vid}', headers=auth_header(admin_token)).status_code == 200
    assert db.query(FollowupSafety).filter_by(visit_id=vid).count() == 0

def test_phq9_symptoms_roundtrip_and_clear(client, admin_token):
    patient = create_patient(client, admin_token)
    visit = create_visit(client, admin_token, patient['id'])
    headers = auth_header(admin_token)
    url = f'/api/visits/{visit}/questionnaire'
    answers = {f'q{i}': 3 for i in range(1, 10)}
    response = client.post(url, headers=headers, json={
        'questionnaire_type': 'phq9', 'phq9_symptoms': '头晕,失眠,其他', **answers})
    assert response.status_code == 200
    assert response.json()['total_score'] == 27
    saved = client.get(url + '/phq9', headers=headers).json()
    assert saved['phq9_symptoms'] == '头晕,失眠,其他'
    assert client.post(url, headers=headers, json={
        'questionnaire_type': 'phq9', 'phq9_symptoms': None, **answers}).status_code == 200
    assert client.get(url + '/phq9', headers=headers).json()['phq9_symptoms'] is None
