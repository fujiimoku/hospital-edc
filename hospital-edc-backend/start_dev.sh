#!/bin/sh
# 开发环境启动后端（uvicorn 必须在 hospital-edc-backend 目录下运行：
# app 模块和 .env 都在这里）
cd "$(dirname "$0")"
exec /e/hospital-edc/venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
