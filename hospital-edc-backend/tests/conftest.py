# -*- coding: utf-8 -*-
"""pytest 公共夹具：SQLite 内存库 + TestClient + 种子数据。

用法：在 hospital-edc-backend 目录下运行
    python -m pytest tests/ -v
"""
import os
import sys

# 必须在导入 app 之前设置环境变量（Settings 在导入时读取）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "pytest-fernet-key")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.center import Center
from app.models.user import User
from app.dependencies import hash_password

# SQLite 内存库：StaticPool 保证所有连接共享同一个 :memory: 实例
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture()
def db():
    """每个测试一个独立会话（同库共享，测试自行清理或用唯一数据）。"""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def seed(_create_tables):  # 依赖表创建；种子数据只写一次
    """写入两个中心 + 各角色账号（幂等）。"""
    s = _TestSessionLocal()
    try:
        if not s.query(Center).filter(Center.center_code == "TJ-01").first():
            s.add(Center(center_code="TJ-01", center_name="测试主中心", is_main_center=True))
        if not s.query(Center).filter(Center.center_code == "TJ-02").first():
            s.add(Center(center_code="TJ-02", center_name="测试分中心", is_main_center=False))
        s.commit()
        c1 = s.query(Center).filter(Center.center_code == "TJ-01").first()
        c2 = s.query(Center).filter(Center.center_code == "TJ-02").first()

        users = [
            ("admin", "main_admin", c1.id),
            ("researcher1", "researcher", c1.id),
            ("qc1", "qc", c1.id),
            ("researcher2", "researcher", c2.id),
        ]
        for username, role, center_id in users:
            if not s.query(User).filter(User.username == username).first():
                s.add(User(
                    username=username,
                    hashed_password=hash_password("Test@123"),
                    full_name=username,
                    role=role,
                    center_id=center_id,
                    is_active=1,
                ))
        s.commit()
        yield {"c1": c1.id, "c2": c2.id}
    finally:
        s.close()


@pytest.fixture()
def client(db):
    """TestClient，数据库依赖替换为 SQLite 内存库。"""
    def _override_get_db():
        session = _TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def login_token(client, username, password="Test@123"):
    """登录并返回 access_token。"""
    r = client.post(
        "/api/auth/login",
        data={"username": username, "password": password, "grant_type": "password"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client, seed):
    return login_token(client, "admin")


@pytest.fixture()
def researcher1_token(client, seed):
    return login_token(client, "researcher1")


@pytest.fixture()
def qc1_token(client, seed):
    return login_token(client, "qc1")


@pytest.fixture()
def researcher2_token(client, seed):
    return login_token(client, "researcher2")
