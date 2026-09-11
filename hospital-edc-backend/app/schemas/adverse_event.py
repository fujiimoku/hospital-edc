from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class AdverseEventCreate(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    term: str
    onset_date: date
    end_date: Optional[date] = None
    severity: Optional[str] = None          # mild | moderate | severe
    is_serious: bool = False
    relation: Optional[str] = None          # definite | probable | possible | unlikely | unrelated
    outcome: Optional[str] = None           # recovered | recovering | not_recovered | death | unknown
    action_taken: Optional[str] = None
    description: Optional[str] = None


class AdverseEventUpdate(BaseModel):
    visit_id: Optional[int] = None
    term: Optional[str] = None
    onset_date: Optional[date] = None
    end_date: Optional[date] = None
    severity: Optional[str] = None
    is_serious: Optional[bool] = None
    relation: Optional[str] = None
    outcome: Optional[str] = None
    action_taken: Optional[str] = None
    description: Optional[str] = None


class AdverseEventOut(BaseModel):
    id: int
    patient_id: int
    visit_id: Optional[int]
    term: str
    onset_date: date
    end_date: Optional[date]
    severity: Optional[str]
    is_serious: bool
    relation: Optional[str]
    outcome: Optional[str]
    action_taken: Optional[str]
    description: Optional[str]
    created_by: Optional[int]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}
