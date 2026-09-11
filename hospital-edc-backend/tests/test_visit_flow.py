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
    """draft → submitted → qc_passed → signed → locked →（unlock）→ signed"""
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

    # 解锁回到 signed，可再次修改
    r = client.post(f"/api/visits/{vid}/unlock", headers=auth_header(admin_token))
    assert r.status_code == 200 and r.json()["status"] == "signed"
    r = client.post(f"/api/visits/{vid}/physical-exam", headers=auth_header(admin_token),
                    json={"height_cm": 171})
    assert r.status_code == 200

    # 收尾：重新锁定，避免影响其他测试
    client.post(f"/api/visits/{vid}/lock", headers=auth_header(admin_token))


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
