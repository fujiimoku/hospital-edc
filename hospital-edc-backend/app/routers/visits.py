from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.visit import Visit
from app.models.patient import Patient
from app.schemas.visit import VisitCreate, VisitUpdate, VisitOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/visits", tags=["访视管理"])


@router.get("/", response_model=List[VisitOut])
def list_visits(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取某患者的所有访视记录"""
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
    current_user=Depends(get_current_user),
):
    """创建新访视"""
    patient = db.query(Patient).filter(Patient.id == data.patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")

    # 同一患者不允许重复同类型访视
    existing = (
        db.query(Visit)
        .filter(
            Visit.patient_id == data.patient_id,
            Visit.visit_type == data.visit_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(400, f"该患者已存在 {data.visit_type} 访视记录")

    visit = Visit(
        patient_id=data.patient_id,
        visit_type=data.visit_type,
        visit_date=data.visit_date,
        status="draft",
        created_by=current_user.id,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


@router.get("/{visit_id}", response_model=VisitOut)
def get_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    return visit


@router.put("/{visit_id}", response_model=VisitOut)
def update_visit(
    visit_id: int,
    data: VisitUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    if visit.status == "locked":
        raise HTTPException(400, "该访视已锁定，无法修改")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(visit, key, value)
    db.commit()
    db.refresh(visit)
    return visit


@router.post("/{visit_id}/submit")
def submit_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """将访视状态从 draft 推进到 submitted"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    if visit.status != "draft":
        raise HTTPException(400, f"当前状态 {visit.status} 不可提交")
    visit.status = "submitted"
    db.commit()
    return {"message": "提交成功", "visit_id": visit_id, "status": "submitted"}


@router.post("/{visit_id}/sign")
def sign_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """研究者签名确认"""
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    if visit.status != "submitted":
        raise HTTPException(400, f"当前状态 {visit.status} 不可签名")
    visit.status = "signed"
    db.commit()
    return {"message": "签名成功", "visit_id": visit_id, "status": "signed"}


@router.delete("/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(404, "访视记录不存在")
    if visit.status in ("signed", "locked"):
        raise HTTPException(400, "已签名或锁定的访视不可删除")
    db.delete(visit)
    db.commit()
    return {"message": "删除成功"}
