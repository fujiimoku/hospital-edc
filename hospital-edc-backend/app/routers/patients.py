from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import exists
from typing import Optional, List
from app.database import get_db
from app.models.center import Center
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.consent import ConsentRecord
from app.schemas.patient import PatientCreate, PatientUpdate, PatientOut
from app.dependencies import get_current_user, get_accessible_center_ids
from app.services.patient_code import generate_patient_code
from app.services.audit import log_change, diff_model
from app.utils.crypto import encrypt, decrypt, mask

router = APIRouter(prefix="/api/patients", tags=["患者管理"])

# 可查看明文身份信息的角色（researcher 仅限本中心，见 _apply_privacy）
PLAINTEXT_ROLES = {"main_admin", "center_admin", "researcher"}


def _apply_privacy(patient: Patient, current_user) -> None:
    """按角色组装解密/脱敏后的身份字段（直接写到实例属性上供 PatientOut 读取）。"""
    can_see_plain = (
        current_user.role in PLAINTEXT_ROLES
        and (
            current_user.role == "main_admin"
            or current_user.center_id == patient.center_id
        )
    )
    full_name = decrypt(patient.full_name_encrypted)
    id_card = decrypt(patient.id_card_encrypted)
    patient.full_name = full_name if can_see_plain else mask(full_name, 1)
    patient.id_card = id_card if can_see_plain else mask(id_card, 3)
    patient.phone = patient.phone if can_see_plain else mask(patient.phone, 3)


@router.get("/", response_model=dict)
def list_patients(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = Query(None, description="按患者编号或姓名首字母搜索"),
    status: Optional[str] = Query(None, description="enrolled | completed | dropout | withdrawn"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 获取用户可访问的中心ID列表
    accessible_centers = get_accessible_center_ids(current_user)

    latest_status_sq = (
        db.query(Visit.status)
        .filter(Visit.patient_id == Patient.id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    has_submitted_sq = (
        db.query(Visit.id)
        .filter(Visit.patient_id == Patient.id, Visit.status != "draft")
        .exists()
    )

    has_consent_sq = (
        db.query(ConsentRecord.id)
        .filter(ConsentRecord.patient_id == Patient.id)
        .exists()
    )

    query = db.query(
        Patient,
        has_submitted_sq.label("has_submitted"),
        has_consent_sq.label("has_consent"),
        latest_status_sq.label("latest_visit_status"),
    )

    # 根据用户权限过滤中心
    if accessible_centers is not None:
        query = query.filter(Patient.center_id.in_(accessible_centers))

    if search:
        query = query.filter(
            Patient.patient_code.contains(search)
            | Patient.name_initials.contains(search)
        )
    if status:
        query = query.filter(Patient.status == status)
    total = query.count()
    rows = query.order_by(Patient.id.desc()).offset(skip).limit(limit).all()
    items = []
    for p, has_submitted, has_consent, latest_visit_status in rows:
        _apply_privacy(p, current_user)
        d = PatientOut.model_validate(p).model_dump()
        d["has_submitted"] = bool(has_submitted)
        d["has_consent"] = bool(has_consent)
        d["latest_visit_status"] = latest_visit_status
        items.append(d)
    return {"total": total, "items": items}


@router.post("/", response_model=PatientOut)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 确定患者所属中心：body.center_id → 当前用户中心
    center_id = data.center_id or current_user.center_id
    if not center_id:
        raise HTTPException(400, "无法确定患者所属中心")

    # 检查用户是否有权限在该中心创建患者
    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and center_id not in accessible_centers:
        raise HTTPException(403, "无权在该中心创建患者")

    # 中心信息以数据库实体为准（不信任 body 里的 center_code）
    center = db.query(Center).filter(Center.id == center_id).first()
    if not center or not center.is_active:
        raise HTTPException(400, "所属中心不存在或已停用")

    # 患者编号：按中心前缀 + 4 位流水号（如 TJ01-0001）
    code = generate_patient_code(db, center)

    payload = data.model_dump(
        exclude={"center_code", "center_id", "full_name", "id_card"}
    )
    patient = Patient(
        **payload,
        patient_code=code,
        center_code=center.center_code,
        center_id=center_id,
        full_name_encrypted=encrypt(data.full_name) if data.full_name else None,
        id_card_encrypted=encrypt(data.id_card) if data.id_card else None,
        created_by=current_user.id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    _apply_privacy(patient, current_user)
    return patient


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """首页概况统计"""
    accessible_centers = get_accessible_center_ids(current_user)

    # 基础查询
    patient_query = db.query(Patient)
    if accessible_centers is not None:
        patient_query = patient_query.filter(Patient.center_id.in_(accessible_centers))

    total = patient_query.count()
    enrolled = patient_query.filter(Patient.status == "enrolled").count()

    # draft 访视 = 待录入；submitted = 待签名
    visit_query = db.query(Visit).join(Patient)
    if accessible_centers is not None:
        visit_query = visit_query.filter(Patient.center_id.in_(accessible_centers))

    pending_entry = visit_query.filter(Visit.status == "draft").count()
    pending_sign = visit_query.filter(Visit.status == "submitted").count()

    return {
        "total_patients": total,
        "enrolled": enrolled,
        "pending_entry": pending_entry,
        "pending_sign": pending_sign,
    }


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    # 检查权限
    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and patient.center_id not in accessible_centers:
        raise HTTPException(403, "无权访问该患者")

    has_submitted = (
        db.query(exists().where(Visit.patient_id == patient_id).where(Visit.status != "draft"))
        .scalar()
    )
    has_consent = (
        db.query(exists().where(ConsentRecord.patient_id == patient_id)).scalar()
    )
    latest = (
        db.query(Visit.status)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .first()
    )
    _apply_privacy(patient, current_user)
    out = PatientOut.model_validate(patient).model_dump()
    out["has_submitted"] = bool(has_submitted)
    out["has_consent"] = bool(has_consent)
    out["latest_visit_status"] = latest[0] if latest else None
    return out


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and patient.center_id not in accessible_centers:
        raise HTTPException(403, "无权修改该患者")

    changes = data.model_dump(exclude_unset=True)
    # 敏感字段单独加密处理
    full_name = changes.pop("full_name", None)
    id_card = changes.pop("id_card", None)
    # 患者编号/归属中心不允许通过更新修改
    changes.pop("patient_code", None)
    center_id = changes.pop("center_id", None)
    if center_id is not None:
        if accessible_centers is not None and center_id not in accessible_centers:
            raise HTTPException(403, "无权转移患者到该中心")
        center = db.query(Center).filter(Center.id == center_id).first()
        if not center:
            raise HTTPException(400, "目标中心不存在")
        patient.center_id = center_id
        patient.center_code = center.center_code

    # 字段级审计：先 diff 再应用（敏感字段只记"已修改"不记明文）
    diff = diff_model(patient, changes)
    for key, value in changes.items():
        setattr(patient, key, value)
    if full_name is not None:
        patient.full_name_encrypted = encrypt(full_name)
    if id_card is not None:
        patient.id_card_encrypted = encrypt(id_card)

    log_change(db, current_user, "patients", patient.id, diff, "update")
    if full_name is not None:
        log_change(db, current_user, "patients", patient.id,
                   {"full_name": ("***", "***")}, "update")
    if id_card is not None:
        log_change(db, current_user, "patients", patient.id,
                   {"id_card": ("***", "***")}, "update")

    db.commit()
    db.refresh(patient)
    _apply_privacy(patient, current_user)
    return patient


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and patient.center_id not in accessible_centers:
        raise HTTPException(403, "无权操作该患者")

    patient.status = "withdrawn"
    db.commit()
    return {"message": "患者已标记为退出"}


# ── 嵌套在患者下的访视路由 ─────────────────────────

from app.schemas.visit import VisitCreate, VisitOut  # noqa: E402


@router.get("/{patient_id}/visits", response_model=List[VisitOut])
def list_patient_visits(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取某患者的所有访视记录"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and patient.center_id not in accessible_centers:
        raise HTTPException(403, "无权访问该患者")
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date)
        .all()
    )


@router.post("/{patient_id}/visits", response_model=VisitOut, status_code=201)
def create_patient_visit(
    patient_id: int,
    data: VisitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """为指定患者创建新访视"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    accessible_centers = get_accessible_center_ids(current_user)
    if accessible_centers is not None and patient.center_id not in accessible_centers:
        raise HTTPException(403, "无权在该患者下创建访视")
    # patient_id 以 URL 为准，覆盖 body 中的字段
    data.patient_id = patient_id
    existing = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.visit_type == data.visit_type)
        .first()
    )
    if existing:
        raise HTTPException(400, f"该患者已存在 {data.visit_type} 访视记录")
    visit = Visit(
        patient_id=patient_id,
        visit_type=data.visit_type,
        visit_date=data.visit_date,
        status="draft",
        created_by=current_user.id,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit
