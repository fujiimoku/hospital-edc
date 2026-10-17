import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from app.database import Base
from app.models.center import Center, InvitationCode
from app.models.user import User
from tests.test_crf_alignment import create_patient, create_visit
from tests.conftest import auth_header

ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    spec = importlib.util.spec_from_file_location('entry_test_module', ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_other_conditions_roundtrip(client, admin_token):
    p = create_patient(client, admin_token)
    vid = create_visit(client, admin_token, p['id'])
    headers = auth_header(admin_token)
    url = f'/api/visits/{vid}/comorbidity'
    r = client.post(url, headers=headers, json={'other_conditions': '医院填写其他病情', 'dr_macular': True})
    assert r.status_code == 200, r.text
    r = client.get(f'/api/visits/{vid}/all-forms', headers=headers)
    assert r.json()['comorbidity']['other_conditions'] == '医院填写其他病情'
    assert r.json()['comorbidity']['dr_macular'] is True
    assert client.post(url, headers=headers, json={'other_conditions': '字' * 2001}).status_code == 422


def test_additive_migration_repeated():
    engine = create_engine('sqlite:///:memory:')
    migration = load('alembic/versions/20261017_entry_layout.py')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE comorbidities (id INTEGER PRIMARY KEY, dr_macular BOOLEAN)'))
        conn.execute(text('INSERT INTO comorbidities VALUES (1, 1)'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            conn.execute(text("UPDATE comorbidities SET other_conditions='保留'"))
            migration.upgrade()
        assert conn.execute(text('SELECT dr_macular, other_conditions FROM comorbidities')).one() == (1, '保留')


def test_branch_invites_repeat_and_conflict():
    module = load('scripts/provision_branch_invites.py')
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(username='admin', hashed_password='unused', role='main_admin', is_active=1))
        db.commit()
        first = module.provision(db, 'admin')
        db.commit()
        assert len(first) == 5
        assert first == module.provision(db, 'admin')
        assert db.query(InvitationCode).count() == 5
        assert all(i.max_uses == 1 and i.role == 'researcher' for i in db.query(InvitationCode))
        db.query(Center).filter_by(center_code='TJ-06').one().center_name = '其他医院'
        db.commit()
        with pytest.raises(ValueError, match='冲突'):
            module.provision(db, 'admin')
        db.rollback()
        assert db.query(InvitationCode).count() == 5


def test_disabled_center_invite_rejected(client, db):
    center = Center(center_code='INV-OFF', center_name='停用测试中心', is_active=False)
    db.add(center)
    db.flush()
    db.add(InvitationCode(code='entry-disabled-test', center_id=center.id, role='researcher', max_uses=1, used_count=0, is_active=True))
    db.commit()
    assert client.get('/api/invitation-codes/validate/entry-disabled-test').json()['valid'] is False
    response = client.post('/api/auth/register-with-code', data={
        'username': 'entry_disabled', 'password': 'Test@123', 'full_name': '测试',
        'invitation_code': 'entry-disabled-test'})
    assert response.status_code == 400
    assert db.query(User).filter_by(username='entry_disabled').first() is None
