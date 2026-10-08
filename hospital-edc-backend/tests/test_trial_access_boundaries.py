"""Real-patient trial boundaries that the browser UI cannot enforce on its own."""

from app.dependencies import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from tests.conftest import auth_header, login_token


def _center_admin_token(client, db, center_id):
    username = f"trial_center_admin_{center_id}"
    if not db.query(User).filter(User.username == username).first():
        db.add(User(
            username=username,
            hashed_password=hash_password("Test@123"),
            role="center_admin",
            center_id=center_id,
            is_active=1,
        ))
        db.commit()
    return login_token(client, username)


def _visit_in_center_two(client, researcher2_token):
    patient = client.post(
        "/api/patients/",
        headers=auth_header(researcher2_token),
        json={"name_initials": "TR", "gender": "female"},
    )
    assert patient.status_code == 200, patient.text
    patient_id = patient.json()["id"]
    visit = client.post(
        "/api/visits/",
        headers=auth_header(researcher2_token),
        json={"patient_id": patient_id, "visit_type": "baseline", "visit_date": "2026-09-23"},
    )
    assert visit.status_code == 200, visit.text
    return patient_id, visit.json()["id"]


def test_other_center_cannot_read_visit_forms(client, researcher1_token, researcher2_token):
    _, visit_id = _visit_in_center_two(client, researcher2_token)
    saved = client.post(
        f"/api/visits/{visit_id}/physical-exam",
        headers=auth_header(researcher2_token),
        json={"height_cm": 170},
    )
    assert saved.status_code == 200
    for path in ("physical-exam", "meal-records", "all-forms"):
        response = client.get(
            f"/api/visits/{visit_id}/{path}",
            headers=auth_header(researcher1_token),
        )
        assert response.status_code == 403, path


def test_other_center_cannot_read_or_replace_consent(client, researcher1_token, researcher2_token):
    patient_id, _ = _visit_in_center_two(client, researcher2_token)
    created = client.post(
        f"/api/consent/{patient_id}",
        headers=auth_header(researcher2_token),
        data={"subject_contact": "test-only"},
    )
    assert created.status_code == 200, created.text
    for method in ("get", "post"):
        response = getattr(client, method)(
            f"/api/consent/{patient_id}",
            headers=auth_header(researcher1_token),
        )
        assert response.status_code == 403, method


def test_center_admin_cannot_create_global_admin(client, db, seed):
    token = _center_admin_token(client, db, seed["c1"])
    direct = client.post(
        "/api/auth/register",
        headers=auth_header(token),
        json={"username": "trial_unapproved_admin", "password": "Test@123", "role": "main_admin"},
    )
    assert direct.status_code == 403
    invite = client.post(
        "/api/invitation-codes/",
        headers=auth_header(token),
        json={"center_id": seed["c1"], "role": "main_admin"},
    )
    assert invite.status_code == 403


def test_center_admin_cannot_read_global_audit_log(client, db, seed):
    token = _center_admin_token(client, db, seed["c1"])
    db.add(AuditLog(table_name="trial_access", record_id=1, field_name="-", action="update",
                    new_value="center-two", center_id=seed["c2"]))
    db.commit()
    response = client.get("/api/audit-logs/?table_name=trial_access", headers=auth_header(token))
    assert response.status_code == 403


def test_qc_cannot_change_source_patient_or_visit_data(client, researcher1_token, qc1_token):
    patient = client.post(
        "/api/patients/", headers=auth_header(researcher1_token),
        json={"name_initials": "QC", "gender": "female"},
    )
    assert patient.status_code == 200
    patient_id = patient.json()["id"]
    visit = client.post(
        "/api/visits/", headers=auth_header(researcher1_token),
        json={"patient_id": patient_id, "visit_type": "baseline", "visit_date": "2026-09-23"},
    )
    assert visit.status_code == 200
    visit_id = visit.json()["id"]
    for method, path, payload in (
        ("post", "/api/patients/", {"name_initials": "QC2", "gender": "male"}),
        ("put", f"/api/patients/{patient_id}", {"age": 55}),
        ("post", "/api/visits/", {"patient_id": patient_id, "visit_type": "M6", "visit_date": "2026-09-23"}),
        ("put", f"/api/visits/{visit_id}", {"visit_date": "2026-09-24"}),
        ("post", f"/api/visits/{visit_id}/physical-exam", {"height_cm": 170}),
        ("post", f"/api/consent/{patient_id}", None),
    ):
        kwargs = {"headers": auth_header(qc1_token)}
        if payload is not None:
            kwargs["json"] = payload
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 403, f"{method.upper()} {path}: {response.text}"


def test_one_use_invitation_provisions_account_in_correct_center(client, admin_token, seed):
    invite = client.post(
        "/api/invitation-codes/",
        headers=auth_header(admin_token),
        json={"center_id": seed["c2"], "role": "researcher", "max_uses": 1, "expires_days": 7},
    )
    assert invite.status_code == 200, invite.text
    code = invite.json()["code"]
    data = {"username": "trial_invited_researcher", "password": "Test@123",
            "full_name": "测试研究者", "invitation_code": code}
    registered = client.post("/api/auth/register-with-code", data=data)
    assert registered.status_code == 200, registered.text
    assert registered.json()["role"] == "researcher"
    assert registered.json()["center_id"] == seed["c2"]
    repeated = client.post("/api/auth/register-with-code", data={**data, "username": "trial_second_user"})
    assert repeated.status_code == 400
