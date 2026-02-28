from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.schemas.patient import PatientCreate, PatientUpdate, PatientOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/patients", tags=["患者管理"])


@router.get("/", response_model=dict)
def list_patients(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = Query(None, description="按患者编号或姓名首字母搜索"),
    status: Optional[str] = Query(None, description="enrolled | withdrawn | completed"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(Patient)
    if search:
        query = query.filter(
            Patient.patient_code.contains(search)
            | Patient.name_initials.contains(search)
        )
    if status:
        query = query.filter(Patient.status == status)
    total = query.count()
    items = query.order_by(Patient.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [PatientOut.model_validate(p).model_dump() for p in items]}


@router.post("/", response_model=PatientOut)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 自动生成患者编号：取当前最大 id+1
    last = db.query(Patient).order_by(Patient.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    code = f"{data.center_code}-{next_num:03d}"

    patient = Patient(
        **data.model_dump(exclude={"center_code"}),
        patient_code=code,
        center_code=data.center_code,
        created_by=current_user.id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """首页概况统计"""
    total = db.query(Patient).count()
    enrolled = db.query(Patient).filter(Patient.status == "enrolled").count()
    # draft 访视 = 待录入；submitted = 待签名
    pending_entry = db.query(Visit).filter(Visit.status == "draft").count()
    pending_sign = db.query(Visit).filter(Visit.status == "submitted").count()
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
    return patient


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
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
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
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "患者不存在")
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
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "患者不存在")
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