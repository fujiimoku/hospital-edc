from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), unique=True, nullable=False)

    # 受试者
    subject_signed_date = Column(Date)
    subject_contact = Column(String(50))

    # 法定代理人（可选）
    proxy_name = Column(String(100))
    proxy_signed_date = Column(Date)
    proxy_contact = Column(String(50))

    # 独立见证人（可选）
    witness_name = Column(String(100))
    witness_signed_date = Column(Date)
    witness_contact = Column(String(50))

    # 研究者
    investigator_name = Column(String(100))
    investigator_signed_date = Column(Date)
    investigator_contact = Column(String(50))

    # 扫描件文件路径（上传后保存相对路径）
    scan_file_path = Column(String(500))
    scan_uploaded_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    patient = relationship("Patient", back_populates="consent")