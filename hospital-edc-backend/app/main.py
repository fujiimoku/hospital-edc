from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from app.routers import auth, patients, visits, forms, consent
from app.database import engine, Base
import app.models  # noqa: 确保所有 Model 在启动时被注册

app = FastAPI(
    title="三一照护 EDC 系统 API",
    description="糖尿病研究数据采集系统后端接口",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.on_event("startup")
def on_startup():
    """仅在开发模式下自动建表；生产环境请使用 alembic upgrade head"""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[WARN] 自动建表失败（数据库未就绪？）: {e}")

# 允许前端跨域访问（开发阶段）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(visits.router)
app.include_router(forms.router)
app.include_router(consent.router)

@app.get("/")
def root():
    return {"message": "EDC 系统 API 运行中", "docs": "/api/docs"}