# -*- coding: utf-8 -*-
"""访视状态流转 + 自动校验 + query 闭环"""
from tests.conftest import auth_header


def _create_patient(client, token, tag):
    r = client.post("/api/patients/", headers=auth_header(token), json={
        "name_initials": tag, "full_name": f"流转{tag}", "gender": "female",
        "age": 60, "enrollment_date": "2026-09-01",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _create_visit(client, token, patient_id):
    r = client.post("/api/visits/", headers=auth_header(token), json={
        "patient_id": patient_id, "visit_type": "baseline", "visit_date": "2026-09-02",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_full_state_flow(client, admin_token, qc1_token):
    """draft → submitted → qc_passed → signed → locked →（unlock）→ draft，再审批"""
    p = _create_patient(client, admin_token, "F1")
    v = _create_visit(client, admin_token, p["id"])
    vid = v["id"]

    # 录入异常值：保存成功但返回 warning
    r = client.post(f"/api/visits/{vid}/physical-exam", headers=auth_header(admin_token), json={
        "height_cm": 170, "weight_kg": 80, "sbp_mmhg": 300, "dbp_mmhg": 130,
    })
    assert r.status_code == 200, r.text
    assert r.json()["warnings"], "异常收缩压 300 应产生 warning"
    assert r.json()["bmi"] == 27.7

    # 提交
    r = client.post(f"/api/visits/{vid}/submit", headers=auth_header(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "submitted"

    # qc 提 query → 研究者回答 → qc 关闭
    r = client.post("/api/queries/", headers=auth_header(qc1_token), json={
        "visit_id": vid, "field_name": "sbp_mmhg", "content": "收缩压 300 请复核",
    })
    assert r.status_code == 201, r.text
    qid = r.json()["id"]

    # 有未关闭 query 时 qc-review 被阻断
    r = client.post(f"/api/visits/{vid}/qc-review", headers=auth_header(qc1_token))
    assert r.status_code == 400

    r = client.patch(f"/api/queries/{qid}/answer", headers=auth_header(admin_token),
                     json={"answer": "已复核，患者血压确实偏高"})
    assert r.status_code == 200 and r.json()["status"] == "answered"
    r = client.patch(f"/api/queries/{qid}/close", headers=auth_header(qc1_token))
    assert r.status_code == 200 and r.json()["status"] == "closed"

    # qc-review → sign → lock
    r = client.post(f"/api/visits/{vid}/qc-review", headers=auth_header(qc1_token))
    assert r.status_code == 200 and r.json()["status"] == "qc_passed"
    r = client.post(f"/api/visits/{vid}/sign", headers=auth_header(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "signed"
    r = client.post(f"/api/visits/{vid}/lock", headers=auth_header(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "locked"

    # 锁定后不可修改
    r = client.post(f"/api/visits/{vid}/physical-exam", headers=auth_header(admin_token),
                    json={"height_cm": 171})
    assert r.status_code == 400

    # 解锁必须填写原因并回到草稿，旧签名不再覆盖修改后的数据
    r = client.post(f"/api/visits/{vid}/unlock", headers=auth_header(admin_token),
                    json={"reason": "复核后更正身高"})
    assert r.status_code == 200 and r.json()["status"] == "draft"
    r = client.post(f"/api/visits/{vid}/physical-exam", headers=auth_header(admin_token),
                    json={"height_cm": 171})
    assert r.status_code == 200

    assert client.post(f"/api/visits/{vid}/lock", headers=auth_header(admin_token)).status_code == 400
    for action in ("submit", "qc-review", "sign", "lock"):
        r = client.post(f"/api/visits/{vid}/{action}", headers=auth_header(admin_token))
        assert r.status_code == 200, r.text


def test_questionnaire_scores(client, admin_token):
    """PHQ-9 总分自动计算 + 分级"""
    p = _create_patient(client, admin_token, "Q1")
    v = _create_visit(client, admin_token, p["id"])
    vid = v["id"]

    r = client.post(f"/api/visits/{vid}/questionnaire", headers=auth_header(admin_token), json={
        "questionnaire_type": "phq9",
        "q1": 2, "q2": 1, "q3": 0, "q4": 1, "q5": 0, "q6": 2, "q7": 1, "q8": 0, "q9": 1,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_score"] == 8
    assert body["level"]  # 分级非空

    r = client.post(f"/api/visits/{vid}/questionnaire", headers=auth_header(admin_token), json={
        "questionnaire_type": "gad7",
        "q1": 1, "q2": 2, "q3": 0, "q4": 1, "q5": 0, "q6": 1, "q7": 2,
    })
    assert r.json()["total_score"] == 7


def test_center_isolated_form_access(client, researcher1_token, researcher2_token):
    """分中心研究者不能改他中心患者的访视表单"""
    p2 = _create_patient(client, researcher2_token, "X1")
    v2 = _create_visit(client, researcher2_token, p2["id"])
    r = client.post(f"/api/visits/{v2['id']}/physical-exam",
                    headers=auth_header(researcher1_token), json={"height_cm": 160})
    assert r.status_code == 403

def test_self_withdraw_reason_scope_state_audit_and_resubmit(client, researcher1_token, researcher2_token, qc1_token, admin_token, db):
    from app.models.audit_log import AuditLog
    from app.models.visit import Visit
    p = _create_patient(client, researcher1_token, 'WD1')
    vid = _create_visit(client, researcher1_token, p['id'])['id']
    headers = auth_header(researcher1_token)
    url = f'/api/visits/{vid}'
    assert client.post(url + '/withdraw-submission', headers=headers, json={'reason': '误点提交，尚未填完'}).status_code == 400
    client.post(url + '/physical-exam', headers=headers, json={'height_cm': 170})
    assert client.post(url + '/submit', headers=headers).status_code == 200
    for token in [researcher2_token, qc1_token]:
        assert client.post(url + '/withdraw-submission', headers=auth_header(token), json={'reason': '选项点错，需要重选'}).status_code == 403
    for payload in [{}, {'reason': ''}, {'reason': '   '}, {'reason': 'x' * 501}]:
        assert client.post(url + '/withdraw-submission', headers=headers, json=payload).status_code == 422
    q = client.post('/api/queries/', headers=auth_header(qc1_token), json={
        'visit_id': vid, 'field_name': 'height_cm', 'content': '请核对身高'}).json()
    r = client.post(url + '/withdraw-submission', headers=headers, json={'reason': '信息填错，需要更正'})
    assert r.status_code == 200 and r.json()['status'] == 'draft'
    assert client.get(url + '/physical-exam', headers=headers).json()['height_cm'] == 170
    assert client.post(url + '/physical-exam', headers=headers, json={'height_cm': 171}).status_code == 200
    events = db.query(AuditLog).filter_by(table_name='visits', record_id=vid, action='withdraw_submission').all()
    assert len(events) == 2
    assert any(e.field_name == 'status' and e.old_value == 'submitted' and e.new_value == 'draft' for e in events)
    assert any(e.field_name == 'reopen_reason' and e.new_value == '信息填错，需要更正' for e in events)
    assert all(e.user_id and e.created_at and e.center_id == p['center_id'] for e in events)
    assert client.post(url + '/withdraw-submission', headers=headers, json={'reason': '重复撤回'}).status_code == 400
    assert client.post(url + '/submit', headers=headers).status_code == 200
    assert client.post(url + '/qc-review', headers=auth_header(qc1_token)).status_code == 400
    client.patch(f"/api/queries/{q['id']}/answer", headers=headers, json={'answer': '已核对更正'})
    client.patch(f"/api/queries/{q['id']}/close", headers=auth_header(qc1_token), json={})
    for action, token in [('qc-review', qc1_token), ('sign', researcher1_token), ('lock', admin_token)]:
        assert client.post(url + '/' + action, headers=auth_header(token)).status_code == 200
        # A stale submitted screen must not reopen a newly reviewed or signed visit.
        assert client.post(url + '/withdraw-submission', headers=headers, json={'reason': '选项点错，需要重选'}).status_code == 400
        assert client.post(url + '/reopen', headers=headers, json={'reason': '选项点错，需要重选'}).status_code == 403
    assert client.post(url + '/unlock', headers=auth_header(admin_token), json={'reason': '漏填内容，需要补充'}).status_code == 200

def test_correction_changes_keep_questionnaire_and_batch_history(client, researcher1_token, db):
    import json
    from app.models.audit_log import AuditLog
    p = _create_patient(client, researcher1_token, 'WD2')
    vid = _create_visit(client, researcher1_token, p['id'])['id']
    headers = auth_header(researcher1_token)
    url = f'/api/visits/{vid}'
    assert client.post(url + '/questionnaire', headers=headers, json={'questionnaire_type':'phq9', 'q1':1}).status_code == 200
    assert client.post(url + '/medications', headers=headers, json={'medications':[{'drug_name':'测试药','dose':'1单位'}]}).status_code == 200
    assert client.post(url + '/meal-records', headers=headers, json={'records':[{'meal_time':'早餐','dish_name':'粥'}]}).status_code == 200
    assert client.post(url + '/submit', headers=headers).status_code == 200
    assert client.post(url + '/withdraw-submission', headers=headers, json={'reason':'信息填错，需要更正'}).status_code == 200
    assert client.post(url + '/questionnaire', headers=headers, json={'questionnaire_type':'phq9', 'q1':2}).status_code == 200
    assert client.post(url + '/medications', headers=headers, json={'medications':[{'drug_name':'测试药','dose':'2单位'}]}).status_code == 200
    assert client.post(url + '/meal-records', headers=headers, json={'records':[]}).status_code == 200
    qid = client.get(url + '/questionnaire/phq9', headers=headers).json()['id']
    item = db.query(AuditLog).filter_by(table_name='questionnaires',record_id=qid,field_name='q1',action='update').one()
    assert (item.old_value,item.new_value) == ('1','2')
    rows = db.query(AuditLog).filter_by(table_name='visits',record_id=vid,field_name='medications').order_by(AuditLog.id).all()
    assert json.loads(rows[-1].old_value)[0]['dose'] == '1单位'
    assert json.loads(rows[-1].new_value)[0]['dose'] == '2单位'
    meal = db.query(AuditLog).filter_by(table_name='visits',record_id=vid,field_name='meal_records').order_by(AuditLog.id.desc()).first()
    assert json.loads(meal.old_value)[0]['dish_name'] == '粥'
    assert json.loads(meal.new_value) == []
    assert item.center_id == p['center_id']
