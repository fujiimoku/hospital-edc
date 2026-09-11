"""患者编号生成规则：{中心码去连字符}-{4位流水号}，如 TJ01-0001。"""
import re

from sqlalchemy.orm import Session

from app.models.center import Center
from app.models.patient import Patient


def normalize_center_prefix(center_code: str) -> str:
    """TJ-01 → TJ01（去掉编号中的连字符，统一大写）。"""
    return re.sub(r"-", "", (center_code or "").strip().upper())


def generate_patient_code(db: Session, center: Center) -> str:
    """按中心前缀生成下一个患者编号：查该中心现有最大流水号 +1。"""
    prefix = normalize_center_prefix(center.center_code)
    pattern = f"{prefix}-%"
    last = (
        db.query(Patient.patient_code)
        .filter(Patient.patient_code.like(pattern))
        .order_by(Patient.patient_code.desc())
        .first()
    )
    next_num = 1
    if last and last[0]:
        try:
            next_num = int(last[0].rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            next_num = 1
    return f"{prefix}-{next_num:04d}"
