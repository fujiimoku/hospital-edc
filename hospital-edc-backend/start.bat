@echo off
chcp 65001 >nul
title EDC 后端服务器
set PYTHONPATH=e:\hospital-edc\hospital-edc-backend
set DATABASE_URL=mysql+pymysql://root:edc123456@127.0.0.1/hospital_edc
set SECRET_KEY=3one-care-edc-jwt-secret-key-2026-hospital-research
set ALGORITHM=HS256
set ACCESS_TOKEN_EXPIRE_MINUTES=480
set UPLOAD_DIR=./uploads

cd /d e:\hospital-edc\hospital-edc-backend
echo 正在启动 EDC 后端服务器...
echo 访问地址: http://localhost:8000
echo API文档:  http://localhost:8000/api/docs
echo 按 Ctrl+C 停止服务器
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
