# -*- coding: utf-8 -*-
"""患者 CRUD + 编号规则 + 加密存储 + 中心隔离 + 隐私脱敏"""
from sqlalchemy import text

from tests.conftest import auth_header


def _create(client, token, **overrides):
    payload = {
        "name_initials": "LS",
        "full_name": "李四",
        "id_card": "120103199001019999",
        "phone": "13800001111",
        "gender": "male",
        "age": 55,
        "marital_status": 2,
        "enrollment_date": "2026-09-01",
    }
    payload.update(overrides)
    r = client.post("/api/patients/", headers=auth_header(token), json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_patient_code_sequence(client, admin_token, db):
    """编号规则：中心前缀 TJ-01 → TJ01-0001、TJ01-0002（4 位流水）"""
    p1 = _create(client, admin_token, name_initials="A1", full_name="测试一")
    p2 = _create(client, admin_token, name_initials="A2", full_name="测试二")
    assert p1["patient_code"].startswith("TJ01-")
    seq1 = int(p1["patient_code"].split("-")[1])
    seq2 = int(p2["patient_code"].split("-")[1])
    assert seq2 == seq1 + 1

def test_patient_code_second_center_prefix(client, admin_token, researcher2_token, seed):
    """TJ-02 中心患者编号以 TJ02- 开头"""
    p = _create(client, researcher2_token, name_initials="B1", full_name="测试三")
    assert p["patient_code"].startswith("TJ02-")

def test_full_name_encrypted_at_rest(client, admin_token, db):
    """库内存储的是密文，接口返回的才是明文（管理员）"""
    p = _create(client, admin_token, name_initials="LS", full_name="张三丰", id_card="120103199001011234")
    row = db.execute(
        text("SELECT full_name_encrypted, id_card_encrypted FROM patients WHERE id = :id"),
        {"id": p["id"]},
    ).fetchone()
    assert row[0] and row[0] != "张三丰", "姓名必须加密存储"
    assert row[1] and row[1] != "120103199001011234", "身份证必须加密存储"

def test_center_isolation_list(client, admin_token, researcher1_token, researcher2_token):
    """分中心只能看到本中心患者"""
    _create(client, researcher2_token, name_initials="C1", full_name="中心二患者")
    r = client.get("/api/patients/", headers=auth_header(researcher2_token))
    codes = [i["patient_code"] for i in r.json()["items"]]
    assert codes and all(c.startswith("TJ02-") for c in codes)

    r = client.get("/api/patients/?limit=200", headers=auth_header(researcher1_token))
    codes1 = [i["patient_code"] for i in r.json()["items"]]
    assert all(c.startswith("TJ01-") for c in codes1), "TJ-01 研究者不应看到 TJ-02 患者"

def test_center_isolation_detail(client, researcher1_token, researcher2_token):
    """分中心用户不能读取他中心患者详情"""
    p2 = _create(client, researcher2_token, name_initials="C2", full_name="中心二患者")
    r = client.get(f"/api/patients/{p2['id']}", headers=auth_header(researcher1_token))
    assert r.status_code == 403

def test_update_with_audit(client, admin_token, db):
    """修改年龄应写审计日志（old → new）"""
    p = _create(client, admin_token, name_initials="LS", full_name="测试修改", age=55)
    r = client.put(f"/api/patients/{p['id']}", headers=auth_header(admin_token), json={"age": 56})
    assert r.status_code == 200
    assert r.json()["age"] == 56
    logs = db.execute(
        text("SELECT field_name, old_value, new_value FROM audit_logs "
             "WHERE table_name='patients' AND record_id=:id AND action='update'"),
        {"id": p["id"]},
    ).fetchall()
    age_logs = [l for l in logs if l[0] == "age"]
    assert age_logs and str(age_logs[0][1]) == "55" and str(age_logs[0][2]) == "56"

def test_sensitive_audit_masked(client, admin_token, db):
    """敏感字段（身份证）审计只记 ***"""
    p = _create(client, admin_token, name_initials="LS", full_name="测试脱敏", id_card="120103199001011234")
    r = client.put(f"/api/patients/{p['id']}", headers=auth_header(admin_token),
                   json={"id_card": "120103199001018888"})
    assert r.status_code == 200
    logs = db.execute(
        text("SELECT field_name, old_value, new_value FROM audit_logs "
             "WHERE table_name='patients' AND record_id=:id AND field_name='id_card'"),
        {"id": p["id"]},
    ).fetchall()
    assert logs and logs[0][1] == "***" and logs[0][2] == "***"
