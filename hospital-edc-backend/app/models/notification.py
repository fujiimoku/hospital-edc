from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    """站内通知：随访窗口提醒 / query 提醒等。"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 接收人
    center_id = Column(Integer)
    type = Column(String(30), nullable=False)   # followup_window / query_raised / ...
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )
