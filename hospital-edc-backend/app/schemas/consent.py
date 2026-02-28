from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ConsentOut(BaseModel):
    id: int
    patient_id: int
    subject_signed_date: Optional[date]
    subject_contact: Optional[str]
    proxy_name: Optional[str]
    proxy_signed_date: Optional[date]
    proxy_contact: Optional[str]
    witness_name: Optional[str]
    witness_signed_date: Optional[date]
    witness_contact: Optional[str]
    investigator_name: Optional[str]
    investigator_signed_date: Optional[date]
    investigator_contact: Optional[str]
    scan_file_path: Optional[str]
    scan_uploaded_at: Optional[datetime]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}
