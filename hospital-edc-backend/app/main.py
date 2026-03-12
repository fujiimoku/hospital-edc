from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import auth, patients, visits, forms, consent, centers, invitation_codes
from app.database import engine, Base
import app.models  # noqa: 确保所有 Model 在启动时被注册
import os

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

# 允许前端跨域访问（开发阶段：允许所有来源，含 file:// 本地打开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(visits.router)
app.include_router(forms.router)
app.include_router(consent.router)
app.include_router(centers.router)
app.include_router(invitation_codes.router)

# ── 前端静态文件托管 ──────────────────────────────────────────
# 计算前端目录：main.py → app/ → hospital-edc-backend/ → hospital-edc/
# hospital-edc-frontend 与 hospital-edc-backend 同级
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # hospital-edc-backend/
_FRONTEND_DIR = os.path.join(os.path.dirname(_BASE_DIR), "hospital-edc-frontend")

@app.get("/")
def root():
    """根路径：直接返回前端 index.html"""
    index_path = os.path.join(_FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "EDC 系统 API 运行中", "docs": "/api/docs"}

# 挂载前端静态资源（css / js / pages / 图片等）
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/css",   StaticFiles(directory=os.path.join(_FRONTEND_DIR, "css")),   name="css")
    app.mount("/js",    StaticFiles(directory=os.path.join(_FRONTEND_DIR, "js")),    name="js")
    app.mount("/pages", StaticFiles(directory=os.path.join(_FRONTEND_DIR, "pages")), name="pages")