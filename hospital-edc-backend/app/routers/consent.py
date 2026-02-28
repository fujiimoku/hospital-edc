import os, shutil
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.consent import ConsentRecord
from app.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/consent", tags=["知情同意"])

@router.post("/{patient_id}")
async def save_consent(
    patient_id: int,
    subject_signed_date: str = Form(...),
    investigator_name: str = Form(...),
    investigator_signed_date: str = Form(...),
    scan_file: UploadFile = File(None),   # 扫描件可选上传
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    file_path = None
    if scan_file:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        filename = f"consent_{patient_id}_{scan_file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(scan_file.file, f)

    record = db.query(ConsentRecord).filter(ConsentRecord.patient_id == patient_id).first()
    if record:
        record.subject_signed_date = subject_signed_date
        record.investigator_name = investigator_name
        record.scan_file_path = file_path
    else:
        db.add(ConsentRecord(
            patient_id=patient_id,
            subject_signed_date=subject_signed_date,
            investigator_name=investigator_name,
            scan_file_path=file_path
        ))
    db.commit()
    return {"message": "知情同意保存成功", "file_uploaded": file_path is not None}