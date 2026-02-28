from sqlalchemy import Column, Integer, Float, Date, Boolean, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PhysicalExam(Base):
    __tablename__ = "physical_exams"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), unique=True, nullable=False)

    weight_kg = Column(Float)
    height_cm = Column(Float)
    bmi = Column(Float)          # 后端自动计算
    waist_cm = Column(Float)
    hip_cm = Column(Float)
    heart_rate = Column(Integer)
    sbp_mmhg = Column(Integer)   # 收缩压
    dbp_mmhg = Column(Integer)   # 舒张压

    recorded_at = Column(DateTime, server_default=func.now())
    visit = relationship("Visit", back_populates="physical_exam")


class LabResults(Base):
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), unique=True, nullable=False)

    fasting_glucose = Column(Float)   # 空腹血糖 mmol/L
    hba1c = Column(Float)             # HbA1c %
    tc = Column(Float)                # 总胆固醇
    tg = Column(Float)                # 甘油三酯
    hdl_c = Column(Float)
    ldl_c = Column(Float)
    alt = Column(Float)
    ast = Column(Float)
    scr = Column(Float)               # 血清肌酐 μmol/L
    egfr = Column(Float)
    ua = Column(Float)                # 尿酸
    bun = Column(Float)
    test_date = Column(Date)

    visit = relationship("Visit", back_populates="lab_results")


class Comorbidity(Base):
    __tablename__ = "comorbidities"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), unique=True, nullable=False)

    # 合并症（0=无, 1=有）
    hypertension = Column(Integer, default=0)
    hypertension_date = Column(String(20))
    ckd = Column(Integer, default=0)
    ckd_date = Column(String(20))
    chd = Column(Integer, default=0)          # 冠心病
    chd_date = Column(String(20))
    angina = Column(Integer, default=0)       # 心绞痛
    angina_date = Column(String(20))
    mi = Column(Integer, default=0)           # 心肌梗死
    mi_date = Column(String(20))
    stroke = Column(Integer, default=0)       # 脑卒中
    stroke_date = Column(String(20))

    # 糖尿病并发症
    dr = Column(Integer, default=0)           # 视网膜病变
    dr_date = Column(String(20))
    dr_macular = Column(Boolean, default=False)
    dr_non_proliferative = Column(Boolean, default=False)
    dr_proliferative = Column(Boolean, default=False)

    dn = Column(Integer, default=0)           # 神经病变
    dn_date = Column(String(20))
    dn_peripheral = Column(Boolean, default=False)
    dn_autonomic = Column(Boolean, default=False)

    df = Column(Integer, default=0)           # 糖尿病足
    df_date = Column(String(20))
    df_healed_ulcer = Column(Boolean, default=False)
    df_active_ulcer = Column(Boolean, default=False)

    visit = relationship("Visit", back_populates="comorbidities")


class CostIndicator(Base):
    __tablename__ = "cost_indicators"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), unique=True, nullable=False)

    drug_cost = Column(Float, default=0)        # 药品费
    lab_cost = Column(Float, default=0)         # 检查化验费
    service_cost = Column(Float, default=0)     # 诊疗服务费
    supply_cost = Column(Float, default=0)      # 耗材费（试纸/针头）
    other_cost = Column(Float, default=0)

    visit = relationship("Visit", back_populates="cost_indicators")