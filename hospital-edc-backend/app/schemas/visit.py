from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime


class VisitCreate(BaseModel):
    patient_id: Optional[int] = None   # 通过 URL 传入时可省略
    visit_type: str          # baseline | M6 | M12 | M18 | M24
    visit_date: date


class VisitUpdate(BaseModel):
    visit_date: Optional[date] = None
    status: Optional[str] = None     # draft | submitted | signed | locked


class VisitOut(BaseModel):
    id: int
    patient_id: int
    visit_type: str
    visit_date: date
    status: str
    created_by: Optional[int]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class VisitReopen(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("必须填写更正原因")
        return value
