import os
import shutil
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.consent import ConsentRecord
from app.models.patient import Patient
from app.schemas.consent import ConsentOut
from app.dependencies import get_current_user, get_accessible_center_ids, require_researcher
from app.config import settings
from app.services.audit import log_change, diff_model

router = APIRouter(prefix="/api/consent", tags=["知情同意"])


def _get_accessible_patient(patient_id: int, db: Session, current_user) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, "患者不存在")
    accessible = get_accessible_center_ids(current_user)
    if accessible is not None and patient.center_id not in accessible:
        raise HTTPException(403, "无权访问该患者的知情同意记录")
    return patient


@router.get("/{patient_id}", response_model=ConsentOut)
def get_consent(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _get_accessible_patient(patient_id, db, current_user)
    record = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).first()
    if not record:
        raise HTTPException(404, "暂无知情同意记录")
    return record


@router.post("/{patient_id}", response_model=ConsentOut)
async def save_consent(
    patient_id: int,
    # 知情同意书版本号（如 V1.0）
    consent_version: Optional[str] = Form(None),
    # 受试者
    subject_signed_date: Optional[str] = Form(None),
    subject_contact: Optional[str] = Form(None),
    # 法定代理人（可选）
    proxy_name: Optional[str] = Form(None),
    proxy_signed_date: Optional[str] = Form(None),
    proxy_contact: Optional[str] = Form(None),
    # 独立见证人（可选）
    witness_name: Optional[str] = Form(None),
    witness_signed_date: Optional[str] = Form(None),
    witness_contact: Optional[str] = Form(None),
    # 研究者
    investigator_name: Optional[str] = Form(None),
    investigator_signed_date: Optional[str] = Form(None),
    investigator_contact: Optional[str] = Form(None),
    # 扫描件（可选）
    scan_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_researcher),
):
    patient = _get_accessible_patient(patient_id, db, current_user)

    def _to_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "签署日期无效，请使用有效的 YYYY-MM-DD 日期")

    record = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).first()
    fields = {
        "consent_version": consent_version,
        "subject_signed_date": _to_date(subject_signed_date),
        "subject_contact": subject_contact,
        "proxy_name": proxy_name,
        "proxy_signed_date": _to_date(proxy_signed_date),
        "proxy_contact": proxy_contact,
        "witness_name": witness_name,
        "witness_signed_date": _to_date(witness_signed_date),
        "witness_contact": witness_contact,
        "investigator_name": investigator_name,
        "investigator_signed_date": _to_date(investigator_signed_date),
        "investigator_contact": investigator_contact,
    }
    # All dates must be valid before writing any uploaded file.
    file_path = None
    if scan_file and scan_file.filename:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        filename = f"consent_{patient_id}_{scan_file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(scan_file.file, f)
    if file_path:
        fields["scan_file_path"] = file_path
        fields["scan_uploaded_at"] = datetime.utcnow()

    fields = {k: v for k, v in fields.items() if v is not None}
    if record:
        changes = diff_model(record, fields)
        action = "update"
        for k, v in fields.items():
            setattr(record, k, v)
    else:
        record = ConsentRecord(patient_id=patient_id, **fields)
        db.add(record)
        db.flush()
        changes = {k: (None, v) for k, v in {"patient_id": patient_id, **fields}.items()}
        action = "create"

    log_change(db, current_user, "consent_records", record.id, changes, action,
               center_id=patient.center_id,
               sensitive_fields={"subject_contact", "proxy_name", "proxy_contact",
                                 "witness_name", "witness_contact", "investigator_name",
                                 "investigator_contact", "scan_file_path"})

    db.commit()
    db.refresh(record)
    return record
