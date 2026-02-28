from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False)

    treatment_type = Column(String(50))   # 糖尿病/高血压/降脂/抗血小板/抗凝/其他
    drug_name = Column(String(100))
    route = Column(String(30))            # 口服/皮下注射/静脉注射/吸入/局部
    dose = Column(String(50))             # 剂量+单位，如 "10 mg"
    frequency = Column(String(20))        # QD/BID/TID/QW/Q2W/QM/PRN ...
    start_date = Column(Date)
    end_date = Column(Date)
    is_ongoing = Column(Boolean, default=True)

    visit = relationship("Visit", back_populates="medications")