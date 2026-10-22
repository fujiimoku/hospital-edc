"""Patient-bound source images. No OCR, public file URLs, or automatic extraction of CRF costs."""
import hashlib
import io
import logging
import re
import tempfile
import warnings
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.database import get_db
from app.dependencies import require_researcher, get_accessible_center_ids, get_current_user
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.patient_image import PatientImage
from app.services.audit import log_change
from app.study import GROUP_LETTERS
from app.utils.crypto import decrypt

router = APIRouter(prefix="/api/patients/{patient_id}/images", tags=["患者费用图片"])
MAX_BYTES = 15 * 1024 * 1024
MAX_ZIP_BYTES = 300 * 1024 * 1024
FORMATS = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"), "WEBP": (".webp", "image/webp")}
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def get_patient(patient_id, db, user):
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(404, "患者不存在")
    centers = get_accessible_center_ids(user)
    if centers is not None and patient.center_id not in centers:
        raise HTTPException(403, "无权访问该患者的图片")
    return patient


def get_image_visit(visit_id, patient_id, db, for_update=False):
    query = db.query(Visit).filter_by(id=visit_id, patient_id=patient_id)
    if for_update:
        query = query.with_for_update()
    visit = query.first()
    if visit is None:
        raise HTTPException(404, "该患者没有此访视")
    return visit


def image_path(item):
    root = (Path(settings.UPLOAD_DIR) / "patient_images").resolve()
    path = (root / item.storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, "图片文件不存在，请联系管理员核对备份")
    return path


def safe_part(value):
    return re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', '_', value or '').strip(' .')[:60] or '未填写姓名'


def filename(patient, item=None):
    group = GROUP_LETTERS.get(patient.study_group)
    prefix = f"{group}组" if group else "未分组"
    name = safe_part(decrypt(patient.full_name_encrypted) or patient.name_initials)
    base = f"{prefix}-{name}-{safe_part(patient.patient_code)}"
    return f"{base}-{item.id:06d}{Path(item.storage_key).suffix}" if item else base + '.zip'


def describe(patient, item):
    return {"id": item.id, "patient_id": patient.id, "filename": filename(patient, item),
            "visit_id": item.visit_id, "size_bytes": item.size_bytes, "created_at": item.created_at}


def audit(db, user, patient, image_id, action):
    log_change(db, user, "patient_images", image_id, {"patient_id": (None, patient.id)},
               action, center_id=patient.center_id)


@router.get("")
def list_images(patient_id: int, visit_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_patient(patient_id, db, user)
    query = db.query(PatientImage).filter_by(patient_id=patient.id)
    if visit_id is not None:
        get_image_visit(visit_id, patient.id, db)
        query = query.filter_by(visit_id=visit_id)
    items = query.order_by(PatientImage.id).all()
    return {"items": [describe(patient, i) for i in items], "archive_filename": filename(patient)}


@router.post("", status_code=201)
def upload_image(patient_id: int, visit_id: int | None = None, file: UploadFile = File(...),
                 db: Session = Depends(get_db), user=Depends(require_researcher)):
    patient = get_patient(patient_id, db, user)
    if visit_id is not None:
        visit = get_image_visit(visit_id, patient.id, db, for_update=True)
        if visit.status != "draft":
            raise HTTPException(400, "仅草稿访视可上传费用照片，请先退回更正")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "每张图片不能超过15MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as picture:
                kind = picture.format
                if kind not in FORMATS or picture.width * picture.height > 40_000_000 or getattr(picture, 'n_frames', 1) != 1:
                    raise ValueError()
                picture.verify()
            with Image.open(io.BytesIO(content)) as picture:
                picture.load()  # Reject truncated or undecodable image data as well as false extensions.
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "请选择完整的 JPG、PNG 或 WebP 静态图片（不超过4000万像素）")
    suffix, media_type = FORMATS[kind]
    root = Path(settings.UPLOAD_DIR) / "patient_images"
    root.mkdir(parents=True, exist_ok=True)
    key = uuid4().hex + suffix
    path = root / key
    item = PatientImage(patient_id=patient.id, visit_id=visit_id, storage_key=key, media_type=media_type,
                        size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), uploaded_by=user.id)
    try:
        with path.open('xb') as output:
            output.write(content)
        db.add(item)
        db.flush()
        audit(db, user, patient, item.id, "upload")
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(item)
    return describe(patient, item)


@router.get("/archive")
def download_archive(patient_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_patient(patient_id, db, user)
    items = db.query(PatientImage).filter_by(patient_id=patient.id).order_by(PatientImage.id).all()
    if not items:
        raise HTTPException(404, "该患者暂无图片")
    if sum(i.size_bytes for i in items) > MAX_ZIP_BYTES:
        raise HTTPException(413, "图片总量超过300MB，请使用单张下载")
    archive = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
            for item in items:
                bundle.write(image_path(item), filename(patient, item))
                audit(db, user, patient, item.id, "download_archive")
        db.commit()
        archive.seek(0)
    except Exception:
        db.rollback()
        archive.close()
        raise
    from urllib.parse import quote
    headers = {**PRIVATE_HEADERS, "Content-Disposition": "attachment; filename*=utf-8''" + quote(filename(patient))}
    def chunks():
        try:
            while chunk := archive.read(1024 * 1024):
                yield chunk
        finally:
            archive.close()
    return StreamingResponse(chunks(), media_type='application/zip', headers=headers,
                             background=BackgroundTask(archive.close))


@router.get("/{image_id}/download")
def download_image(patient_id: int, image_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    patient = get_patient(patient_id, db, user)
    item = db.query(PatientImage).filter_by(id=image_id, patient_id=patient.id).first()
    if item is None:
        raise HTTPException(404, "该患者没有这张图片")
    path = image_path(item)
    audit(db, user, patient, item.id, "download")
    db.commit()
    return FileResponse(path, media_type=item.media_type, filename=filename(patient, item), headers=PRIVATE_HEADERS)


@router.delete("/{image_id}")
def delete_image(patient_id: int, image_id: int, db: Session = Depends(get_db), user=Depends(require_researcher)):
    patient = get_patient(patient_id, db, user)
    item = db.query(PatientImage).filter_by(id=image_id, patient_id=patient.id).first()
    if item is None:
        raise HTTPException(404, "该患者没有这张图片")
    if item.visit_id is not None:
        visit = get_image_visit(item.visit_id, patient.id, db, for_update=True)
        if visit.status != "draft":
            raise HTTPException(400, "仅草稿访视可删除费用照片，请先退回更正")
    path = image_path(item)
    # Only hold bytes in memory during the transaction, to restore on a database failure.
    content = path.read_bytes()
    removed = False
    try:
        log_change(db, user, "patient_images", item.id,
                   {"patient_id": (patient.id, None)}, "delete", center_id=patient.center_id)
        db.delete(item)
        db.flush()
        path.unlink()
        removed = True
        db.commit()
    except Exception:
        db.rollback()
        if removed:
            path.write_bytes(content)
        raise
    return {"deleted": True, "id": image_id}
