from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_type = Column(
        Enum("baseline", "M6", "M12", "M18", "M24"),
        nullable=False
    )
    visit_date = Column(Date, nullable=False)
    # 状态流转：draft → submitted → signed → locked
    status = Column(
        Enum("draft", "submitted", "signed", "locked"),
        default="draft"
    )
    created_by = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # 关联
    patient = relationship("Patient", back_populates="visits")
    physical_exam = relationship("PhysicalExam", back_populates="visit", uselist=False)
    lab_results = relationship("LabResults", back_populates="visit", uselist=False)
    comorbidities = relationship("Comorbidity", back_populates="visit", uselist=False)
    medications = relationship("Medication", back_populates="visit")
    cost_indicators = relationship("CostIndicator", back_populates="visit", uselist=False)
    questionnaires = relationship("Questionnaire", back_populates="visit")
    lifestyle = relationship("LifestyleAssessment", back_populates="visit", uselist=False)
    meal_records = relationship("MealRecord", back_populates="visit")