from sqlalchemy import Column, Integer, String, Date, Boolean, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AdverseEvent(Base):
    __tablename__ = "adverse_events"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=True)

    term = Column(String(200), nullable=False)     # 不良事件名称
    onset_date = Column(Date, nullable=False)      # 发生日期
    end_date = Column(Date)                        # 结束日期（未结束为 NULL）
    severity = Column(Enum("mild", "moderate", "severe"))  # 轻/中/重
    is_serious = Column(Boolean, default=False)    # 是否 SAE
    relation = Column(Enum("definite", "probable", "possible", "unlikely", "unrelated"))  # 与研究药物关系
    outcome = Column(Enum("recovered", "recovering", "not_recovered", "death", "unknown"))  # 转归
    action_taken = Column(String(200))             # 采取的措施
    description = Column(Text)                     # 事件描述

    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    patient = relationship("Patient", back_populates="adverse_events")
    visit = relationship("Visit")
