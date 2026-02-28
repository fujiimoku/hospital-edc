from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,       # 自动检测断线重连
    pool_recycle=3600,        # 每小时回收连接，防止 MySQL 超时断开
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI 依赖注入：自动管理数据库会话生命周期"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()