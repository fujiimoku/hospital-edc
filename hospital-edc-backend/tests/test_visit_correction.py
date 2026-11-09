from tests.conftest import auth_header
from tests.test_crf_alignment import create_patient, create_visit
from app.models.visit import Visit
from app.models.audit_log import AuditLog


def test_correct_date_and_delete_draft(client, researcher1_token, researcher2_token, qc1_token, db):
    h=auth_header(researcher1_token)
    pid=create_patient(client,researcher1_token)['id']
    vid=create_visit(client,researcher1_token,pid)
    other=create_visit(client,researcher1_token,pid,'W26')
    url=f'/api/visits/{vid}'
    assert client.delete(url,headers=auth_header(researcher2_token)).status_code==403
    assert client.delete(url,headers=auth_header(qc1_token)).status_code==403
    assert client.put(url,headers=h,json={'visit_date':None}).status_code==422
    assert client.post(url+'/physical-exam',headers=h,json={'height_cm':170}).status_code==200
    assert client.put(url,headers=h,json={'visit_date':'2026-11-09'}).status_code==200
    assert client.get(url+'/all-forms',headers=h).json()['physical_exam']['height_cm']==170
    assert client.delete(url,headers=h).status_code==200
    assert client.get(url,headers=h).status_code==404
    assert client.get(f'/api/visits/{other}',headers=h).status_code==200
    assert client.get(f'/api/patients/{pid}',headers=h).status_code==200
    assert db.query(AuditLog).filter_by(table_name='visits',record_id=vid,action='delete').count()==1
    assert create_visit(client,researcher1_token,pid)!=vid


def test_submitted_and_conflicting_dates_blocked(client,admin_token,db):
    h=auth_header(admin_token);pid=create_patient(client,admin_token)['id']
    one=create_visit(client,admin_token,pid,'interim','2026-11-01')
    two=create_visit(client,admin_token,pid,'interim','2026-11-02')
    assert client.put(f'/api/visits/{two}',headers=h,json={'visit_date':'2026-11-01'}).status_code==400
    for state in ['submitted','qc_passed','signed','locked']:
        visit=db.get(Visit,one);visit.status=state;db.commit()
        assert client.delete(f'/api/visits/{one}',headers=h).status_code==400
        assert client.put(f'/api/visits/{one}',headers=h,json={'visit_date':'2026-11-03'}).status_code==400


def test_photo_blocks_deletion_without_removing_photo(client, admin_token):
    from tests.test_patient_images import picture
    h=auth_header(admin_token);pid=create_patient(client,admin_token)['id']
    vid=create_visit(client,admin_token,pid)
    image=client.post(f'/api/patients/{pid}/images?visit_id={vid}',headers=h,files={'file':('test.png',picture(),'image/png')})
    assert image.status_code==201
    assert client.delete(f'/api/visits/{vid}',headers=h).status_code==400
    assert client.get(f'/api/patients/{pid}/images/{image.json()["id"]}/download',headers=h).status_code==200
