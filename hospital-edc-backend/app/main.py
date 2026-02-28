from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, patients, visits, forms, consent
from app.database import engine, Base

# 创建所有表（开发阶段用，生产建议用 Alembic）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="三一照护 EDC 系统 API",
    description="糖尿病研究数据采集系统后端接口",
    version="1.0.0",
    docs_url="/api/docs",       # Swagger UI 地址
    redoc_url="/api/redoc",
)

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
app.include_router(forms.router)
app.include_router(consent.router)

@app.get("/")
def root():
    return {"message": "EDC 系统 API 运行中", "docs": "/api/docs"}