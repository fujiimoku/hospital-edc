from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class QueryCreate(BaseModel):
    visit_id: int
    field_name: str
    content: str


class QueryAnswer(BaseModel):
    answer: str


class QueryOut(BaseModel):
    id: int
    visit_id: int
    field_name: str
    content: str
    status: str
    raised_by: Optional[int]
    answered_by: Optional[int]
    answer: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}
