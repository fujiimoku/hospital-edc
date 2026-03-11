from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    # 角色：researcher=研究者, qc=质控员, center_admin=分中心管理员, main_admin=总中心管理员
    role = Column(Enum("researcher", "qc", "center_admin", "main_admin"), default="researcher")
    center_id = Column(Integer, ForeignKey("centers.id"), nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    center = relationship("Center", back_populates="users")