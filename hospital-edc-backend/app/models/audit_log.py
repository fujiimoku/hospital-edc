from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    """审计留痕（中国 GCP）：字段级前后值 + 动作。"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(50), nullable=False)    # patients / visits / forms / ...
    record_id = Column(Integer, nullable=False)
    field_name = Column(String(50), nullable=False, default="-")
    old_value = Column(Text)
    new_value = Column(Text)
    # create / update / delete / lock / unlock / submit / sign / qc_review / export / login / user_manage
    action = Column(String(20), nullable=False)
    user_id = Column(Integer)
    center_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_logs_table_record", "table_name", "record_id"),
    )
