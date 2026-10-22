from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.visit import Visit
from app.models.patient import Patient
from app.models.query import Query
from app.schemas.visit import VisitCreate, VisitUpdate, VisitOut, VisitReopen
from app.dependencies import (
    get_current_user, get_accessible_center_ids,
    require_admin, require_main_admin, require_qc, require_researcher,
)
from app.services.audit import log_action, log_change, diff_model

router = APIRouter(prefix="/api/visits", tags=["访视管理"])


def _get_visit_with_access(visit_id: int, db: Session, current_user, for_update=False) -> Visit:
    """取访视并校验中心隔离。"""
    query = db.query(Visit).filter(Visit.id == visit_id)
    if for_update:
        query = query.populate_existing().with_for_update()
    visit = query.first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None:
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        if patient is None or patient.center_id not in accessible:
            raise HTTPException(403, "无权访问该访视")
    return visit


@router.get("/", response_model=List[VisitOut])
def list_visits(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取某患者的所有访视记录（中心隔离）"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and patient.center_id not in accessible:
        raise HTTPException(403, "无权访问该患者")
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date)
        .all()
    )


@router.post("/", response_model=VisitOut)
def create_visit(
    data: VisitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    """创建新访视"""
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and patient.center_id not in accessible:
        raise HTTPException(403, "无权在该患者下创建访视")

    # 同一患者不允许重复同类型访视
    existing = (
        db.query(Visit)
        .filter(
            Visit.patient_id == data.patient_id,
            Visit.visit_type == data.visit_type,
        )
        .first()
    )
    if data.visit_type == "interim":
        existing = db.query(Visit).filter(
            Visit.patient_id == patient.id, Visit.visit_type == "interim",
            Visit.visit_date == data.visit_date,
        ).first()
    if existing:
        raise HTTPException(400, "该患者已存在此主访视或同日中间采集记录")

    visit = Visit(
        patient_id=data.patient_id,
        visit_type=data.visit_type,
        visit_date=data.visit_date,
        status="draft",
        created_by=current_user.id,
    )
    db.add(visit)
    db.flush()
    log_action(db, current_user, "visits", visit.id, "create",
               f"创建访视 {data.visit_type} {data.visit_date}")
    db.commit()
    db.refresh(visit)
    return visit


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _get_visit_with_access(visit_id, db, current_user)


@router.put("/{visit_id}", response_model=VisitOut)
def update_visit(
    visit_id: int,
    data: VisitUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    if visit.status != "draft":
        raise HTTPException(400, "仅草稿访视可修改，请先由总管理员退回草稿")
    changes = data.model_dump(exclude_unset=True)
    # 状态不允许通过 PUT 直接改（需走状态流转端点）
    changes.pop("status", None)
    diff = diff_model(visit, changes)
    for key, value in changes.items():
        setattr(visit, key, value)
    if diff:
        log_change(db, current_user, "visits", visit.id, diff, "update")
    db.commit()
    db.refresh(visit)
    return visit


# ── 状态流转 ────────────────────────────────────────

def _transition(visit: Visit, expected: str, to: str):
    if visit.status != expected:
        raise HTTPException(400, f"当前状态 {visit.status} 不可执行该操作（需 {expected}）")


def _require_closed_queries(db, visit_id):
    if db.query(Query).filter(Query.visit_id == visit_id, Query.status != "closed").count():
        raise HTTPException(400, "该访视还有未关闭的质疑，无法继续审核、签名或锁定")


@router.post("/{visit_id}/submit")
def submit_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    """研究者提交：draft → submitted"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    _transition(visit, "draft", "submitted")
    visit.status = "submitted"
    log_action(db, current_user, "visits", visit.id, "submit", "draft→submitted")
    db.commit()
    return {"message": "提交成功", "visit_id": visit_id, "status": "submitted"}


@router.post("/{visit_id}/qc-review")
def qc_review_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_qc),
):
    """质控审核：submitted → qc_passed（要求全部 query 已关闭）"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    _transition(visit, "submitted", "qc_passed")
    open_count = (
        db.query(Query)
        .filter(Query.visit_id == visit_id, Query.status != "closed")
        .count()
    )
    if open_count > 0:
        raise HTTPException(400, f"该访视还有 {open_count} 条未关闭的质疑（query），无法通过质控")
    visit.status = "qc_passed"
    log_action(db, current_user, "visits", visit.id, "qc_review", "submitted→qc_passed")
    db.commit()
    return {"message": "质控审核通过", "visit_id": visit_id, "status": "qc_passed"}


@router.post("/{visit_id}/sign")
def sign_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    """研究者签名确认：qc_passed → signed"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    _transition(visit, "qc_passed", "signed")
    _require_closed_queries(db, visit_id)
    visit.status = "signed"
    log_action(db, current_user, "visits", visit.id, "sign", "qc_passed→signed")
    db.commit()
    return {"message": "签名成功", "visit_id": visit_id, "status": "signed"}


@router.post("/{visit_id}/lock")
def lock_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_qc),
):
    """质控员或管理员锁定：signed → locked"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    _transition(visit, "signed", "locked")
    _require_closed_queries(db, visit_id)
    visit.status = "locked"
    log_action(db, current_user, "visits", visit.id, "lock", "signed→locked")
    db.commit()
    return {"message": "锁定成功", "visit_id": visit_id, "status": "locked"}


@router.post("/{visit_id}/unlock")
def unlock_visit(
    visit_id: int,
    data: VisitReopen,
    db: Session = Depends(get_db),
    current_user=Depends(require_main_admin),
):
    """总中心管理员解锁更正：locked → draft，旧审核/签名不再有效。"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    _transition(visit, "locked", "draft")
    return _reopen(db, current_user, visit, data.reason, "unlock")


def _reopen(db, current_user, visit, reason, action):
    previous = visit.status
    visit.status = "draft"
    log_change(db, current_user, "visits", visit.id,
               {"status": (previous, "draft"), "reopen_reason": (None, reason)}, action,
               center_id=visit.patient.center_id)
    db.commit()
    return {"message": "已退回草稿，更正后须重新提交、审核和签名", "visit_id": visit.id, "status": "draft"}


@router.post("/{visit_id}/withdraw-submission")
def withdraw_submission(visit_id: int, data: VisitReopen, db: Session = Depends(get_db),
                        current_user=Depends(require_researcher)):
    """录入人员可撤回尚未通过审核的提交；与审核操作共用行锁。"""
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    if visit.status != "submitted":
        raise HTTPException(400, "仅待审核访视可自行撤回；已通过审核、签名或锁定的访视请联系总管理员退回更正")
    return _reopen(db, current_user, visit, data.reason, "withdraw_submission")


@router.post("/{visit_id}/reopen")
def reopen_visit(visit_id: int, data: VisitReopen, db: Session = Depends(get_db),
                 current_user=Depends(require_main_admin)):
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    if visit.status not in ("submitted", "qc_passed", "signed"):
        raise HTTPException(400, "只能退回已提交、质控通过或已签名的访视；锁定访视请先解锁")
    return _reopen(db, current_user, visit, data.reason, "reopen")


@router.delete("/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    visit = _get_visit_with_access(visit_id, db, current_user, for_update=True)
    if visit.status != "draft":
        raise HTTPException(400, "仅草稿访视可删除")
    db.delete(visit)
    db.commit()
    return {"message": "删除成功"}
