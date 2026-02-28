from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False)
    # 类型：phq9 / gad7 / eq5d / dtsq
    questionnaire_type = Column(String(20), nullable=False)

    # PHQ-9 / GAD-7：9或7道题，每题 0-3
    q1 = Column(Integer)
    q2 = Column(Integer)
    q3 = Column(Integer)
    q4 = Column(Integer)
    q5 = Column(Integer)
    q6 = Column(Integer)
    q7 = Column(Integer)
    q8 = Column(Integer)   # PHQ-9 专用
    q9 = Column(Integer)   # PHQ-9 专用
    total_score = Column(Float)   # 后端自动计算

    # EQ-5D-5L 专用（5个维度，每个1-5）
    eq_mobility = Column(Integer)        # 行动能力
    eq_self_care = Column(Integer)       # 自我照顾
    eq_usual_activity = Column(Integer)  # 日常活动
    eq_pain = Column(Integer)            # 疼痛/不舒服
    eq_anxiety = Column(Integer)         # 焦虑/沮丧
    eq_vas_score = Column(Integer)       # 刻度尺 0-100

    # DTSQ 专用（10题，每题1-5）
    dtsq_open_text = Column(Text)        # 开放性问题答案

    # PHQ-9 就诊主要症状（位掩码存储）
    phq9_symptoms = Column(String(100))  # 逗号分隔，如 "头晕,失眠"

    completed_at = Column(DateTime, server_default=func.now())
    visit = relationship("Visit", back_populates="questionnaires")