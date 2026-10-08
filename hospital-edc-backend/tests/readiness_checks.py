"""Pre-release acceptance checks, also collected through test_release_safety.py.

Uses the existing isolated SQLite fixtures. Failures are release findings, not
expected failures: do not hide them with xfail. No production data is accessed.
"""
from datetime import timedelta
import importlib
import pytest
from tests.conftest import auth_header, _test_engine
from app.dependencies import create_access_token
from app.models.user import User
from app.models.audit_log import AuditLog


@pytest.fixture(autouse=True)
def isolated_startup_engine(monkeypatch):
    # Startup create_all must use the same thread-safe isolated engine as requests.
    monkeypatch.setattr(importlib.import_module('app.main'), 'engine', _test_engine)


def patient(client, token):
    r = client.post('/api/patients/', headers=auth_header(token),
                    json={'name_initials': 'UAT', 'gender': 'female'})
    assert r.status_code == 200, r.text
    return r.json()['id']


def visit(client, token, pid):
    r = client.post('/api/visits/', headers=auth_header(token), json={
        'patient_id': pid, 'visit_type': 'baseline', 'visit_date': '2026-10-08'})
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_static_resources(client):
    for path in ['/', '/js/config.js', '/js/auth.js', '/css/main.css',
                 '/pages/visit-entry.html', '/pages/consent.html', '/pages/export.html']:
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.content) > 100, path


def test_expired_token_rejected(client, seed):
    token = create_access_token({'sub': 'researcher1'}, timedelta(seconds=-60))
    assert client.get('/api/auth/me', headers=auth_header(token)).status_code == 401


def test_disabled_account_existing_token_rejected(client, db, researcher1_token):
    user = db.query(User).filter_by(username='researcher1').one()
    try:
        user.is_active = 0
        db.commit()
        assert client.get('/api/auth/me', headers=auth_header(researcher1_token)).status_code == 401
        assert client.post('/api/auth/login', data={
            'username': 'researcher1', 'password': 'Test@123'}).status_code == 403
    finally:
        user.is_active = 1
        db.commit()


def test_adverse_event_center_and_role_boundaries(client, researcher1_token, researcher2_token, qc1_token):
    pid = patient(client, researcher1_token)
    payload = {'patient_id': pid, 'term': 'Synthetic UAT event', 'onset_date': '2026-10-08'}
    r = client.post('/api/adverse-events/', headers=auth_header(researcher1_token), json=payload)
    assert r.status_code == 201
    eid = r.json()['id']
    for method, path, body in [
        ('get', f'/api/adverse-events/{eid}', None),
        ('put', f'/api/adverse-events/{eid}', {'term': 'changed'}),
        ('delete', f'/api/adverse-events/{eid}', None),
        ('post', '/api/adverse-events/', payload),
    ]:
        kw = {'headers': auth_header(researcher2_token)}
        if body is not None:
            kw['json'] = body
        assert getattr(client, method)(path, **kw).status_code == 403
    assert client.post('/api/adverse-events/', headers=auth_header(qc1_token), json=payload).status_code == 403


@pytest.mark.parametrize('state', ['submitted', 'qc_passed', 'signed'])
def test_reviewed_data_cannot_change_without_reopening(client, researcher1_token, qc1_token, state):
    pid = patient(client, researcher1_token)
    vid = visit(client, researcher1_token, pid)
    h = auth_header(researcher1_token)
    assert client.post(f'/api/visits/{vid}/physical-exam', headers=h, json={'height_cm': 170}).status_code == 200
    assert client.post(f'/api/visits/{vid}/submit', headers=h).status_code == 200
    if state in ('qc_passed', 'signed'):
        assert client.post(f'/api/visits/{vid}/qc-review', headers=auth_header(qc1_token)).status_code == 200
    if state == 'signed':
        assert client.post(f'/api/visits/{vid}/sign', headers=h).status_code == 200
    response = client.post(f'/api/visits/{vid}/physical-exam', headers=h, json={'height_cm': 180})
    assert response.status_code in (400, 403, 409), f'{state}: modification accepted ({response.status_code})'


def test_consent_invalid_date_rejected(client, researcher1_token):
    pid = patient(client, researcher1_token)
    r = client.post(f'/api/consent/{pid}', headers=auth_header(researcher1_token),
                    data={'subject_signed_date': '2026-02-30'})
    assert r.status_code in (400, 422), f'Invalid date silently accepted: {r.status_code}'


@pytest.mark.parametrize('kind', ['consent', 'adverse_event'])
def test_sensitive_record_creation_is_audited(client, db, researcher1_token, kind):
    pid = patient(client, researcher1_token)
    before = db.query(AuditLog).count()
    if kind == 'consent':
        r = client.post(f'/api/consent/{pid}', headers=auth_header(researcher1_token),
                        data={'consent_version': 'UAT-v1', 'subject_signed_date': '2026-10-08'})
        assert r.status_code == 200
    else:
        r = client.post('/api/adverse-events/', headers=auth_header(researcher1_token),
                        json={'patient_id': pid, 'term': 'Synthetic UAT event', 'onset_date': '2026-10-08'})
        assert r.status_code == 201
    assert db.query(AuditLog).count() > before, f'No audit record for {kind}'


def test_adverse_event_cannot_reference_other_center_visit(client, researcher1_token, researcher2_token):
    p1 = patient(client, researcher1_token)
    p2 = patient(client, researcher2_token)
    v2 = visit(client, researcher2_token, p2)
    r = client.post('/api/adverse-events/', headers=auth_header(researcher1_token), json={
        'patient_id': p1, 'visit_id': v2, 'term': 'Synthetic UAT event', 'onset_date': '2026-10-08'})
    assert r.status_code in (400, 403, 422), f'Cross-patient visit reference accepted: {r.status_code}'


def test_answered_but_unclosed_query_blocks_review(client, researcher1_token, qc1_token):
    pid = patient(client, researcher1_token)
    vid = visit(client, researcher1_token, pid)
    rh, qh = auth_header(researcher1_token), auth_header(qc1_token)
    assert client.post(f'/api/visits/{vid}/submit', headers=rh).status_code == 200
    r = client.post('/api/queries/', headers=qh, json={
        'visit_id': vid, 'field_name': 'sbp_mmhg', 'content': 'UAT clarification'})
    assert r.status_code == 201
    qid = r.json()['id']
    r = client.patch(f'/api/queries/{qid}/answer', headers=rh, json={'answer': 'UAT response'})
    assert r.status_code == 200 and r.json()['status'] == 'answered'
    r = client.post(f'/api/visits/{vid}/qc-review', headers=qh)
    assert r.status_code in (400, 409), f'Unclosed query allowed review: {r.status_code}'
