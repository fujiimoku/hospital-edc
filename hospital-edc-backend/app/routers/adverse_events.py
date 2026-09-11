from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.adverse_event import AdverseEvent
from app.models.patient import Patient
from app.schemas.adverse_event import AdverseEventCreate, AdverseEventUpdate, AdverseEventOut
from app.dependencies import get_current_user, get_accessible_center_ids

router = APIRouter(prefix="/api/adverse-events", tags=["不良事件"])


def _get_accessible_patient(db: Session, patient_id: int, current_user) -> Patient:
    """取患者并校验中心隔离。"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and patient.center_id not in accessible:
        raise HTTPException(403, "无权访问该患者的不良事件")
    return patient


@router.get("/", response_model=List[AdverseEventOut])
def list_adverse_events(
    patient_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """不良事件列表（可按患者过滤），按中心隔离。"""
    query = db.query(AdverseEvent).join(Patient)
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None:
        query = query.filter(Patient.center_id.in_(accessible))
    if patient_id:
        _get_accessible_patient(db, patient_id, current_user)
        query = query.filter(AdverseEvent.patient_id == patient_id)
    return query.order_by(AdverseEvent.onset_date.desc(), AdverseEvent.id.desc()).all()


@router.get("/{ae_id}", response_model=AdverseEventOut)
def get_adverse_event(
    ae_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ae = db.query(AdverseEvent).filter(AdverseEvent.id == ae_id).first()
    if not ae:
        raise HTTPException(404, "不良事件不存在")
    _get_accessible_patient(db, ae.patient_id, current_user)
    return ae


@router.post("/", response_model=AdverseEventOut, status_code=201)
def create_adverse_event(
    data: AdverseEventCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_accessible_patient(db, data.patient_id, current_user)
    ae = AdverseEvent(**data.model_dump(), created_by=current_user.id)
    db.add(ae)
    db.commit()
    db.refresh(ae)
    return ae


@router.put("/{ae_id}", response_model=AdverseEventOut)
def update_adverse_event(
    ae_id: int,
    data: AdverseEventUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ae = db.query(AdverseEvent).filter(AdverseEvent.id == ae_id).first()
    if not ae:
        raise HTTPException(404, "不良事件不存在")
    _get_accessible_patient(db, ae.patient_id, current_user)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(ae, key, value)
    db.commit()
    db.refresh(ae)
    return ae


@router.delete("/{ae_id}")
def delete_adverse_event(
    ae_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ae = db.query(AdverseEvent).filter(AdverseEvent.id == ae_id).first()
    if not ae:
        raise HTTPException(404, "不良事件不存在")
    _get_accessible_patient(db, ae.patient_id, current_user)
    db.delete(ae)
    db.commit()
    return {"message": "不良事件已删除"}
