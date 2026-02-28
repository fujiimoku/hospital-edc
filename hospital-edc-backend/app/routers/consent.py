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
from app.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/consent", tags=["知情同意"])


@router.get("/{patient_id}", response_model=ConsentOut)
def get_consent(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).first()
    if not record:
        raise HTTPException(404, "暂无知情同意记录")
    return record


@router.post("/{patient_id}", response_model=ConsentOut)
async def save_consent(
    patient_id: int,
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
    current_user=Depends(get_current_user),
):
    # 确认患者存在
    if not db.query(Patient).filter(Patient.id == patient_id).first():
        raise HTTPException(404, "患者不存在")

    # 处理文件上传
    file_path = None
    if scan_file and scan_file.filename:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        filename = f"consent_{patient_id}_{scan_file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(scan_file.file, f)

    def _to_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            return None

    record = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).first()
    fields = {
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
    if file_path:
        fields["scan_file_path"] = file_path
        fields["scan_uploaded_at"] = datetime.utcnow()

    if record:
        for k, v in fields.items():
            if v is not None:
                setattr(record, k, v)
    else:
        record = ConsentRecord(patient_id=patient_id, **{k: v for k, v in fields.items() if v is not None})
        db.add(record)

    db.commit()
    db.refresh(record)
    return record