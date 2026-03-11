from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InvitationCodeCreate(BaseModel):
    center_id: int
    role: str
    max_uses: int = 1
    expires_days: Optional[int] = None


class InvitationCodeOut(BaseModel):
    id: int
    code: str
    center_id: int
    role: str
    max_uses: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
