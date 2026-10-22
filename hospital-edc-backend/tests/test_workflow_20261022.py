from datetime import date
import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.conftest import auth_header
from tests.test_crf_alignment import create_patient, create_visit
from app.models.visit import Visit
from app.models.patient import Patient
from app.models.audit_log import AuditLog


def test_approved_membership_paging_tracking_and_name_scope(client, researcher1_token, researcher2_token, qc1_token, admin_token, db):
    p = create_patient(client, researcher1_token, name_initials='ROUND22A', full_name='测试汉字姓名', phone='13812345678')
    v = create_visit(client, researcher1_token, p['id'], 'baseline', '2026-01-01')
    draft = create_visit(client, researcher1_token, p['id'], 'W12', '2026-04-01')
    def listing(token, extra=''):
        return client.get('/api/patients/?search=ROUND22A&approved_only=true&limit=1'+extra, headers=auth_header(token)).json()
    assert listing(admin_token)['total'] == 0
    db.get(Visit, v).status = 'submitted'; db.commit()
    assert listing(admin_token)['total'] == 0
    db.get(Visit, v).status = 'qc_passed'; db.commit()
    data = listing(qc1_token)
    assert data['total'] == 1 and data['items'][0]['latest_visit_status'] == 'draft'
    assert data['items'][0]['full_name'] == '测试汉字姓名'
    assert data['items'][0]['phone'] != '13812345678'
    assert listing(researcher2_token)['total'] == 0
    assert listing(admin_token, '&skip=1')['items'] == []
    url = f"/api/patients/{p['id']}/tracking"
    assert client.put(url, headers=auth_header(researcher2_token), json={'tracking_status':'completed'}).status_code == 403
    assert client.put(url, headers=auth_header(qc1_token), json={'tracking_status':'completed'}).status_code == 200
    assert listing(admin_token, '&tracking_status=pending')['total'] == 0
    assert listing(admin_token, '&tracking_status=completed')['total'] == 1
    db.expire_all()
    assert db.get(Visit, draft).status == 'draft'
    assert db.get(Patient, p['id']).phone == '13812345678'
    assert db.query(AuditLog).filter_by(table_name='patients',record_id=p['id'],field_name='tracking_status').count() == 1


def test_copy_previous_date_order_all_medications_and_no_history_mutation(client, researcher1_token, researcher2_token):
    h = auth_header(researcher1_token)
    p = create_patient(client, researcher1_token)
    target = create_visit(client, researcher1_token, p['id'], 'W26', '2026-08-01')
    early = create_visit(client, researcher1_token, p['id'], 'baseline', '2026-01-01')
    previous = create_visit(client, researcher1_token, p['id'], 'W12', '2026-04-01')
    future = create_visit(client, researcher1_token, p['id'], 'interim', '2026-09-01')
    med = {'drug_name':'历史停用药','route':'口服','end_date':'2026-03-31','is_ongoing':False}
    for vid, name in [(early,'更早'),(previous,med['drug_name']),(future,'之后')]:
        assert client.post(f'/api/visits/{vid}/medications',headers=h,json={'medications':[{**med,'drug_name':name}]}).status_code == 200
    url=f'/api/visits/{target}/previous-medications'
    result=client.get(url,headers=h).json()
    assert result['source_visit']['id'] == previous
    assert result['medications'][0]['drug_name'] == med['drug_name']
    assert result['medications'][0]['is_ongoing'] is False
    assert result['medications'][0]['end_date'] == med['end_date']
    assert 'visit_id' not in result['medications'][0]
    assert client.get(url,headers=auth_header(researcher2_token)).status_code == 403
    assert client.get(f'/api/visits/{early}/previous-medications',headers=h).json()['source_visit'] is None
    copied=result['medications']; copied[0]['drug_name']='本次修改'
    assert client.post(f'/api/visits/{target}/medications',headers=h,json={'medications':copied}).status_code == 200
    assert client.get(url,headers=h).json()['medications'][0]['drug_name'] == med['drug_name']


def test_qc_lock_scope_and_export_always_masked(client, researcher1_token, researcher2_token, qc1_token, admin_token, db):
    p=create_patient(client,researcher1_token)
    v=create_visit(client,researcher1_token,p['id'])
    url=f'/api/visits/{v}/lock'
    assert client.post(url,headers=auth_header(qc1_token)).status_code == 400
    db.get(Visit,v).status='signed';db.commit()
    assert client.post(url,headers=auth_header(researcher1_token)).status_code == 403
    assert client.post(url,headers=auth_header(qc1_token)).status_code == 200
    p2=create_patient(client,researcher2_token)
    v2=create_visit(client,researcher2_token,p2['id'])
    db.get(Visit,v2).status='signed';db.commit()
    assert client.post(f'/api/visits/{v2}/lock',headers=auth_header(qc1_token)).status_code == 403
    for token in (admin_token,qc1_token,researcher1_token):
        assert client.get('/api/export/?deidentify=false',headers=auth_header(token)).status_code == 403


def test_tracking_migration_repeatable_preserves_existing_rows():
    path=Path(__file__).parents[1]/'alembic/versions/20261022_workflow.py'
    spec=importlib.util.spec_from_file_location('workflow_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE patients (id INTEGER PRIMARY KEY, name TEXT)'))
        connection.execute(text("INSERT INTO patients VALUES (1,'untouched')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();module.upgrade()
        assert tuple(connection.execute(text('SELECT * FROM patients')).first()) == (1,'untouched','pending')


def test_single_use_invites_cover_main_and_branches_and_reuse(db, seed):
    from scripts.provision_study_invites import provision
    rows=provision(db,'admin')
    assert {row[1] for row in rows} == {'researcher','qc'}
    assert {'测试主中心','测试分中心'} <= {row[0] for row in rows}
    assert provision(db,'admin') == rows
