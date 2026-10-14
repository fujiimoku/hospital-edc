import importlib.util
import sys
from pathlib import Path
from datetime import date

import pytest
from sqlalchemy import create_engine, select, insert, event
from app.database import Base
import app.models
from app.dependencies import verify_password

scripts = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('reset_trial_data', scripts / 'reset_trial_data.py')
reset = importlib.util.module_from_spec(spec); spec.loader.exec_module(reset)


@pytest.fixture
def trial_db():
    engine = create_engine('sqlite:///:memory:')
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    t = Base.metadata.tables
    with engine.begin() as c:
        c.execute(insert(t['centers']), [{'id':1,'center_code':'TEST1','center_name':'合成中心1'},
                                        {'id':2,'center_code':'TEST2','center_name':'合成中心2'}])
        c.execute(insert(t['users']), [{'id':1,'username':'old_admin','hashed_password':'unused','role':'main_admin','center_id':1},
                                      {'id':2,'username':'old_user','hashed_password':'unused','role':'researcher','center_id':2}])
        c.execute(insert(t['patients']).values(id=1,patient_code='TEST-1',center_id=1,gender='female'))
        c.execute(insert(t['visits']).values(id=1,patient_id=1,visit_type='baseline',visit_date=date(2026,1,1)))
        c.execute(insert(t['followup_safety']).values(id=1,visit_id=1))
        c.execute(insert(t['consent_records']).values(id=1,patient_id=1))
        c.execute(insert(t['patient_images']).values(id=1,patient_id=1,storage_key='synthetic.png',media_type='image/png',size_bytes=5,sha256='0'*64,uploaded_by=2))
        c.execute(insert(t['invitation_codes']).values(id=1,code='SYNTHETIC',center_id=1,role='researcher'))
        c.execute(insert(t['notifications']).values(id=1,user_id=2,type='followup_window',content='合成通知'))
        c.execute(insert(t['audit_logs']).values(id=1,table_name='patients',record_id=1,action='create',user_id=2))
    return engine


def test_reset_preserves_history_disables_old_access_and_creates_admin(trial_db):
    t = Base.metadata.tables
    with trial_db.begin() as c:
        before=reset.snapshot(c)
        reset.reset_database(c,before,'hospital_admin','Synthetic-Password-2026',1,[],True)
    with trial_db.connect() as c:
        for name in reset.CLINICAL_TABLES:
            assert not c.execute(select(t[name])).first()
        users=c.execute(select(t['users']).order_by(t['users'].c.id)).mappings().all()
        assert [u['is_active'] for u in users]==[0,0,1]
        assert users[2]['username']=='hospital_admin' and users[2]['role']=='main_admin'
        assert verify_password('Synthetic-Password-2026',users[2]['hashed_password'])
        assert [r.is_active for r in c.execute(select(t['centers']))]==[False,False]
        assert c.execute(select(t['invitation_codes'].c.is_active)).scalar_one()==False
        assert len(c.execute(select(t['audit_logs'])).all())==2


@pytest.mark.parametrize('failure', ['changed_data','existing_user','short_password','unknown_table'])
def test_reset_refuses_unreviewed_conditions_without_partial_deletion(trial_db,failure):
    t=Base.metadata.tables
    with trial_db.begin() as c:
        before=reset.snapshot(c)
        if failure=='changed_data': c.execute(t['patients'].update().values(age=55))
        if failure=='unknown_table': c.exec_driver_sql('CREATE TABLE unknown_research_data (id INTEGER PRIMARY KEY)')
    with pytest.raises((RuntimeError,ValueError)):
        with trial_db.begin() as c:
            reset.reset_database(c,before,'old_admin' if failure=='existing_user' else 'hospital_admin',
                                 'short' if failure=='short_password' else 'Synthetic-Password-2026',1,[],True)
    with trial_db.connect() as c:
        assert c.execute(select(t['patients'].c.id)).scalar_one()==1
        assert len(c.execute(select(t['patient_images'])).all())==1
        assert all(r.is_active for r in c.execute(select(t['users'])))


def test_database_failure_after_deletion_rolls_back_everything(trial_db):
    t=Base.metadata.tables
    with trial_db.connect() as c:
        before=reset.snapshot(c)
    def fail_insert(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO users'):
            raise RuntimeError('simulated account creation failure')
    event.listen(trial_db,'before_cursor_execute',fail_insert)
    try:
        with pytest.raises(RuntimeError,match='simulated'):
            with trial_db.begin() as c:
                reset.reset_database(c,before,'hospital_admin','Synthetic-Password-2026',1,[],True)
    finally:
        event.remove(trial_db,'before_cursor_execute',fail_insert)
    with trial_db.connect() as c:
        reset.compare(c,before)
