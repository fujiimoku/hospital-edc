from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Center(Base):
    __tablename__ = "centers"

    id = Column(Integer, primary_key=True, index=True)
    center_code = Column(String(20), unique=True, nullable=False, index=True)
    center_name = Column(String(100), nullable=False)
    is_main_center = Column(Boolean, default=False)
    contact_person = Column(String(100))
    contact_phone = Column(String(20))
    contact_email = Column(String(100))
    address = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    users = relationship("User", back_populates="center")
    patients = relationship("Patient", back_populates="center")


class InvitationCode(Base):
    __tablename__ = "invitation_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    center_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
