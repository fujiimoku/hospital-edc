from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    # 角色：researcher=研究者, qc=质控员, admin=管理员
    role = Column(Enum("researcher", "qc", "admin"), default="researcher")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())