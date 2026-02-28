from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.patient import Patient
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/patients", tags=["患者管理"])

@router.get("/")
def list_patients(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = Query(None),   # 按编号或首字母搜索
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Patient)
    if search:
        query = query.filter(
            Patient.patient_code.contains(search) |
            Patient.name_initials.contains(search)
        )
    if status:
        query = query.filter(Patient.status == status)
    total = query.count()
    patients = query.order_by(Patient.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": patients}

@router.post("/")
def create_patient(data: dict, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # 自动生成患者编号
    last = db.query(Patient).order_by(Patient.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    code = f"CHN-017-{next_num:03d}"

    patient = Patient(**data, patient_code=code, created_by=current_user.id)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

@router.get("/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    return patient

@router.put("/{patient_id}")
def update_patient(patient_id: int, data: dict, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    for key, value in data.items():
        setattr(patient, key, value)
    db.commit()
    return patient