# -*- coding: utf-8 -*-
"""认证与权限测试"""
from tests.conftest import login_token, auth_header


def test_login_ok(client, seed):
    token = login_token(client, "admin")
    assert token

def test_login_wrong_password(client, seed):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401

def test_login_unknown_user(client, seed):
    r = client.post("/api/auth/login", data={"username": "nobody", "password": "x"})
    assert r.status_code == 401

def test_me(client, admin_token):
    r = client.get("/api/auth/me", headers=auth_header(admin_token))
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "main_admin"

def test_no_token_401(client, seed):
    r = client.get("/api/patients/")
    assert r.status_code == 401

def test_invalid_token_401(client, seed):
    r = client.get("/api/patients/", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401

def test_qc_cannot_create_patient_for_other_center(client, seed, qc1_token):
    """质控员（TJ-01）不能在 TJ-02 建患者"""
    c2 = seed["c2"]
    r = client.post("/api/patients/", headers=auth_header(qc1_token), json={
        "name_initials": "ZS", "gender": "male", "center_id": c2,
    })
    assert r.status_code == 403
