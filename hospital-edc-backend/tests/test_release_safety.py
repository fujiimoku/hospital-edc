"""Make all readiness regressions part of the default suite, plus mutation edges."""
from tests.readiness_checks import *  # noqa: F403; collect the 12 release regressions
from app.models.consent import ConsentRecord
from app.models.adverse_event import AdverseEvent
from app.models.visit import Visit
from app.config import settings
from app.models.query import Query
from pathlib import Path
from uuid import uuid4


@pytest.fixture
def upload_test_dir():
    # Default mkdir permissions are compatible with the managed Windows workspace.
    directory = Path(__file__).resolve().parents[2] / 'artifacts' / 'fixes-20261008' / f'uploads-{uuid4().hex}'
    directory.mkdir(parents=True)
    yield directory
    # This fixture expects no files; never recursively remove unexpected contents.
    if not any(directory.iterdir()):
        directory.rmdir()


def advance(client, token, vid, state):
    actions = [('submit', 'submitted'), ('qc-review', 'qc_passed'), ('sign', 'signed'), ('lock', 'locked')]
    for action, destination in actions:
        r = client.post(f'/api/visits/{vid}/{action}', headers=auth_header(token))
        assert r.status_code == 200, r.text
        if destination == state:
            break


@pytest.mark.parametrize('state', ['submitted', 'qc_passed', 'signed', 'locked'])
def test_all_source_write_routes_blocked_and_reopen_audited(client, db, admin_token, researcher1_token, state):
    pid = patient(client, researcher1_token)
    vid = visit(client, researcher1_token, pid)
    advance(client, admin_token, vid, state)
    h = auth_header(researcher1_token)
    before = client.get(f'/api/visits/{vid}/all-forms', headers=h).json()
    audit_count = db.query(AuditLog).count()
    for suffix, payload in [
        ('physical-exam', {'height_cm': 180}), ('lab-results', {'hba1c': 7}),
        ('comorbidity', {'hypertension': 1}), ('cost-indicators', {'drug_cost': 1}),
        ('medications', {'medications': []}), ('questionnaire', {'questionnaire_type': 'phq9', 'q1': 1}),
        ('lifestyle', {'bad_habits': 'test'}), ('meal-records', {'records': []}),
        ('meals', {'records': []}),
    ]:
        r = client.post(f'/api/visits/{vid}/{suffix}', headers=h, json=payload)
        assert r.status_code == 400, (suffix, r.text)
    assert client.put(f'/api/visits/{vid}', headers=h, json={'visit_date': '2026-10-09'}).status_code == 400
    assert client.delete(f'/api/visits/{vid}', headers=h).status_code == 400
    assert client.get(f'/api/visits/{vid}/all-forms', headers=h).json() == before
    assert db.query(AuditLog).count() == audit_count
    action = 'unlock' if state == 'locked' else 'reopen'
    url = f'/api/visits/{vid}/{action}'
    assert client.post(url, headers=h, json={'reason': 'correction'}).status_code == 403
    assert client.post(url, headers=auth_header(admin_token), json={'reason': '  '}).status_code == 422
    assert client.post(url, headers=auth_header(admin_token)).status_code == 422
    r = client.post(url, headers=auth_header(admin_token), json={'reason': 'Correct source data'})
    assert r.status_code == 200 and r.json()['status'] == 'draft'
    assert client.post(f'/api/visits/{vid}/physical-exam', headers=h, json={'height_cm': 180}).status_code == 200
    assert client.post(f'/api/visits/{vid}/sign', headers=h).status_code == 400
    assert client.post(f'/api/visits/{vid}/lock', headers=auth_header(admin_token)).status_code == 400
    logs = db.query(AuditLog).filter_by(table_name='visits', record_id=vid, action=action).all()
    assert any(x.field_name == 'status' and x.old_value == state and x.new_value == 'draft' for x in logs)
    assert any(x.field_name == 'reopen_reason' and x.new_value == 'Correct source data' for x in logs)
    advance(client, admin_token, vid, 'locked')


@pytest.mark.parametrize('field', ['subject_signed_date', 'proxy_signed_date', 'witness_signed_date', 'investigator_signed_date'])
def test_bad_consent_date_preserves_record_audit_and_upload(client, db, researcher1_token, field, upload_test_dir, monkeypatch):
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(upload_test_dir))
    pid = patient(client, researcher1_token)
    h = auth_header(researcher1_token)
    r = client.post(f'/api/consent/{pid}', headers=h, data={field: '2024-02-29', 'consent_version': 'v1'})
    assert r.status_code == 200
    before = r.json()
    count = db.query(AuditLog).count()
    for value in ('2026-02-30', 'not-a-date', '2026-13-01'):
        r = client.post(f'/api/consent/{pid}', headers=h, data={field: value, 'consent_version': 'v2'},
                        files={'scan_file': ('test.pdf', b'synthetic file', 'application/pdf')})
        assert r.status_code == 422
        assert client.get(f'/api/consent/{pid}', headers=h).json() == before
    assert list(upload_test_dir.iterdir()) == []
    assert db.query(AuditLog).count() == count


@pytest.mark.parametrize('other', ['same_center', 'other_center', 'missing'])
def test_ae_create_and_update_validate_visit_without_side_effects(client, db, researcher1_token, researcher2_token, other):
    h = auth_header(researcher1_token)
    pid = patient(client, researcher1_token)
    own_vid = visit(client, researcher1_token, pid)
    if other == 'missing':
        bad_vid = 99999999
    else:
        token = researcher1_token if other == 'same_center' else researcher2_token
        bad_vid = visit(client, token, patient(client, token))
    payload = {'patient_id': pid, 'visit_id': own_vid, 'term': 'Synthetic AE', 'onset_date': '2026-10-08'}
    r = client.post('/api/adverse-events/', headers=h, json=payload)
    assert r.status_code == 201
    eid = r.json()['id']
    count = db.query(AuditLog).count()
    row_count = db.query(AdverseEvent).count()
    assert client.post('/api/adverse-events/', headers=h, json={**payload, 'visit_id': bad_vid}).status_code == 400
    assert client.put(f'/api/adverse-events/{eid}', headers=h, json={'visit_id': bad_vid, 'term': 'bad'}).status_code == 400
    assert client.get(f'/api/adverse-events/{eid}', headers=h).json()['visit_id'] == own_vid
    assert db.query(AuditLog).count() == count
    assert db.query(AdverseEvent).count() == row_count
    assert client.put(f'/api/adverse-events/{eid}', headers=h, json={'visit_id': None}).status_code == 200


def test_consent_audit_masks_identifiers_and_uses_target_center(client, db, admin_token, researcher2_token, seed):
    pid = patient(client, researcher2_token)
    h = auth_header(admin_token)
    r = client.post(f'/api/consent/{pid}', headers=h, data={'consent_version': 'v1', 'proxy_name': 'SyntheticPrivateName'})
    assert r.status_code == 200
    rid = r.json()['id']
    assert client.post(f'/api/consent/{pid}', headers=h, data={'consent_version': 'v2', 'proxy_name': 'ChangedPrivateName'}).status_code == 200
    logs = db.query(AuditLog).filter_by(table_name='consent_records', record_id=rid).all()
    assert {x.action for x in logs} == {'create', 'update'}
    assert all(x.center_id == seed['c2'] and x.user_id and x.created_at for x in logs)
    assert any(x.field_name == 'consent_version' and x.old_value == 'v1' and x.new_value == 'v2' for x in logs)
    assert all(x.new_value == '***' for x in logs if x.field_name == 'proxy_name')
    count = len(logs)
    client.post(f'/api/consent/{pid}', headers=h, data={'consent_version': 'v2'})
    assert db.query(AuditLog).filter_by(table_name='consent_records', record_id=rid).count() == count


def test_ae_audit_survives_delete_with_actor_and_diff(client, db, admin_token, researcher2_token, seed):
    pid = patient(client, researcher2_token)
    h = auth_header(admin_token)
    r = client.post('/api/adverse-events/', headers=h, json={
        'patient_id': pid, 'term': 'Synthetic AE', 'severity': 'mild',
        'description': 'Private narrative', 'onset_date': '2026-10-08'})
    assert r.status_code == 201
    eid = r.json()['id']
    assert client.put(f'/api/adverse-events/{eid}', headers=h, json={'severity': 'severe'}).status_code == 200
    assert client.delete(f'/api/adverse-events/{eid}', headers=h).status_code == 200
    assert client.get(f'/api/adverse-events/{eid}', headers=h).status_code == 404
    logs = db.query(AuditLog).filter_by(table_name='adverse_events', record_id=eid).all()
    assert {x.action for x in logs} == {'create', 'update', 'delete'}
    assert all(x.center_id == seed['c2'] and x.user_id and x.created_at for x in logs)
    assert any(x.field_name == 'severity' and x.old_value == 'mild' and x.new_value == 'severe' for x in logs)
    assert any(x.action == 'delete' and x.field_name == 'severity' and x.old_value == 'severe' and x.new_value is None for x in logs)
    assert all(v != 'Private narrative' for x in logs for v in (x.old_value, x.new_value))


def test_closed_query_allows_review_and_cannot_add_after_review(client, researcher1_token, qc1_token):
    pid = patient(client, researcher1_token)
    vid = visit(client, researcher1_token, pid)
    rh, qh = auth_header(researcher1_token), auth_header(qc1_token)
    client.post(f'/api/visits/{vid}/submit', headers=rh)
    payload = {'visit_id': vid, 'field_name': 'sbp_mmhg', 'content': 'UAT clarify'}
    r = client.post('/api/queries/', headers=qh, json=payload)
    assert r.status_code == 201
    qid = r.json()['id']
    assert client.post(f'/api/visits/{vid}/qc-review', headers=qh).status_code == 400
    client.patch(f'/api/queries/{qid}/answer', headers=rh, json={'answer': 'Verified'})
    assert client.post(f'/api/visits/{vid}/qc-review', headers=qh).status_code == 400
    assert client.patch(f'/api/queries/{qid}/close', headers=qh).status_code == 200
    assert client.post(f'/api/visits/{vid}/qc-review', headers=qh).status_code == 200
    assert client.post('/api/queries/', headers=qh, json=payload).status_code == 400


@pytest.mark.parametrize('state,action', [('qc_passed', 'sign'), ('signed', 'lock')])
def test_legacy_unclosed_queries_block_later_approvals(client, db, admin_token, state, action):
    vid = visit(client, admin_token, patient(client, admin_token))
    advance(client, admin_token, vid, state)
    db.add(Query(visit_id=vid, field_name='sbp_mmhg', content='Legacy unresolved', status='answered'))
    db.commit()
    assert client.post(f'/api/visits/{vid}/{action}', headers=auth_header(admin_token)).status_code == 400
    assert client.get(f'/api/visits/{vid}', headers=auth_header(admin_token)).json()['status'] == state
