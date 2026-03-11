from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CenterBase(BaseModel):
    center_code: str
    center_name: str
    is_main_center: bool = False
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None


class CenterCreate(CenterBase):
    pass


class CenterUpdate(BaseModel):
    center_name: Optional[str] = None
    is_main_center: Optional[bool] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class CenterOut(CenterBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
