from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "researcher"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    role: str
    is_active: int
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
