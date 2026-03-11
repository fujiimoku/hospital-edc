from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class PatientCreate(BaseModel):
    name_initials: str
    full_name_encrypted: Optional[str] = None
    gender: str                          # "male" | "female"
    age: Optional[int] = None
    visit_number: Optional[str] = None
    center_code: Optional[str] = "CHN-017"
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


class PatientUpdate(PatientCreate):
    gender: Optional[str] = None
    name_initials: Optional[str] = None


class PatientOut(BaseModel):
    id: int
    patient_code: str
    center_code: Optional[str]
    center_id: int
    name_initials: Optional[str]
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
    # 录入状态（由后端计算，便于前端展示/禁用入口）
    has_submitted: bool = False
    has_consent: bool = False
    latest_visit_status: Optional[str] = None
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}
