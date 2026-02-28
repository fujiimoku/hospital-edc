from sqlalchemy import Column, Integer, Float, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import json

class LifestyleAssessment(Base):
    __tablename__ = "lifestyle_assessments"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), unique=True, nullable=False)

    # 饮食评估（10题，各2.5/5/7.5/10分）
    diet_scores_json = Column(Text)       # JSON 存储 10 个题目的分值
    diet_total = Column(Float)            # 自动求和
    diet_level = Column(String(20))       # 差/尚可/一般/良好

    # 运动评估（5题）
    exercise_scores_json = Column(Text)
    exercise_total = Column(Float)
    exercise_level = Column(String(20))

    # 不良饮食习惯（多选，逗号分隔）
    bad_habits = Column(String(200))      # 如 "不食早餐,外卖至上"

    # 膳食基本信息（勾选项）
    meal_basic_info_json = Column(Text)

    visit = relationship("Visit", back_populates="lifestyle")


class MealRecord(Base):
    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False)

    meal_time = Column(String(20))        # 早餐/早加餐/午餐/午加餐/晚餐/晚加餐
    dish_name = Column(String(100))       # 菜肴名称
    ingredients = Column(String(200))     # 食物成分
    raw_cooked = Column(String(10))       # 生/熟
    estimated_amount = Column(String(50)) # 食物估量 如 "200g"

    visit = relationship("Visit", back_populates="meal_records")