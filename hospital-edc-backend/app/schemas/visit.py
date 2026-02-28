from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class VisitCreate(BaseModel):
    patient_id: int
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
