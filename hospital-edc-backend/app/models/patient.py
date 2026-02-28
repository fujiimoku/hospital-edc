from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_code = Column(String(20), unique=True, nullable=False, index=True)
    # 例：CHN-017-161
    center_code = Column(String(20), default="CHN-017")

    # 姓名拼音首字母（脱敏）
    name_initials = Column(String(10))
    # 完整姓名（加密存储，实际项目可用 AES 加密）
    full_name_encrypted = Column(String(255))

    gender = Column(Enum("male", "female"), nullable=False)
    age = Column(Integer)
    visit_number = Column(String(50))         # 就诊号

    # 社会学信息
    employment_status = Column(Integer)       # 1在职 2无工作 3退休
    education_level = Column(Integer)         # 1文盲 2小学 3中学 4大学
    insurance_coverage = Column(Integer)      # 1无 2商保 3社保 4均有
    smoking_status = Column(Integer)          # 1不吸烟 2曾经 3目前
    smoking_per_day = Column(Integer)
    drinking_status = Column(Integer)         # 1不 2既往 3社交 4大量
    drinking_per_day = Column(Integer)

    consent_date = Column(Date)
    enrollment_date = Column(Date)
    status = Column(Enum("enrolled", "withdrawn", "completed"), default="enrolled")

    created_by = Column(Integer)              # 创建者 user_id
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # 关联
    visits = relationship("Visit", back_populates="patient")
    consent = relationship("ConsentRecord", back_populates="patient", uselist=False)