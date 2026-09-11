from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Query(Base):
    """质控疑问（Data Query）：质控员对某访视某字段提出质疑，研究者回答。"""
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False, index=True)
    field_name = Column(String(50), nullable=False)     # 被质疑字段
    content = Column(Text, nullable=False)              # 质疑内容
    status = Column(Enum("open", "answered", "closed"), default="open")
    raised_by = Column(Integer)                         # 质控员 user_id
    answered_by = Column(Integer)                       # 研究者 user_id
    answer = Column(Text)                               # 研究者回答
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
