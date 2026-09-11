from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class PatientCreate(BaseModel):
    name_initials: str
    full_name: Optional[str] = None        # 明文入参，后端加密存储
    id_card: Optional[str] = None          # 身份证号（明文入参，后端加密存储）
    phone: Optional[str] = None
    gender: str                          # "male" | "female"
    age: Optional[int] = None
    visit_number: Optional[str] = None
    center_code: Optional[str] = None     # 仅作展示；实际归属以 center_id/当前用户中心为准
    center_id: Optional[int] = None
    marital_status: Optional[int] = None  # 1未婚 2已婚 3离异 4丧偶

    employment_status: Optional[int] = None
    education_level: Optional[int] = None
    insurance_coverage: Optional[int] = None
    smoking_status: Optional[int] = None
    smoking_per_day: Optional[int] = None
    drinking_status: Optional[int] = None
    drinking_per_day: Optional[int] = None

    consent_date: Optional[date] = None
    enrollment_date: Optional[date] = None


class PatientUpdate(BaseModel):
    name_initials: Optional[str] = None
    full_name: Optional[str] = None
    id_card: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    visit_number: Optional[str] = None
    marital_status: Optional[int] = None
    center_id: Optional[int] = None

    employment_status: Optional[int] = None
    education_level: Optional[int] = None
    insurance_coverage: Optional[int] = None
    smoking_status: Optional[int] = None
    smoking_per_day: Optional[int] = None
    drinking_status: Optional[int] = None
    drinking_per_day: Optional[int] = None

    consent_date: Optional[date] = None
    enrollment_date: Optional[date] = None
    status: Optional[str] = None
    withdraw_reason: Optional[str] = None
    withdraw_date: Optional[date] = None


class PatientOut(BaseModel):
    id: int
    patient_code: str
    center_code: Optional[str]
    center_id: int
    name_initials: Optional[str]
    # 解密/脱敏后的姓名与身份证（由后端按权限组装，不直接来自 DB 列）
    full_name: Optional[str] = None
    id_card: Optional[str] = None
    phone: Optional[str] = None
    marital_status: Optional[int] = None
    gender: str
    age: Optional[int]
    visit_number: Optional[str]
    employment_status: Optional[int]
    education_level: Optional[int]
    insurance_coverage: Optional[int]
    smoking_status: Optional[int]
    smoking_per_day: Optional[int]
    drinking_status: Optional[int]
    drinking_per_day: Optional[int]
    consent_date: Optional[date]
    enrollment_date: Optional[date]
    status: Optional[str]
    withdraw_reason: Optional[str] = None
    withdraw_date: Optional[date] = None
    # 录入状态（由后端计算，便于前端展示/禁用入口）
    has_submitted: bool = False
    has_consent: bool = False
    latest_visit_status: Optional[str] = None
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}
