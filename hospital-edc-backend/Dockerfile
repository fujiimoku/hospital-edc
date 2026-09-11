# EDC 后端镜像：一份镜像多实例复用（每实例独立 .env 决定端口/库/密钥）
FROM python:3.13-slim

WORKDIR /app

# 先装依赖（利用镜像层缓存）
COPY hospital-edc-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝后端代码（构建上下文为仓库根目录）
COPY hospital-edc-backend/app ./app
COPY hospital-edc-backend/alembic ./alembic
COPY hospital-edc-backend/alembic.ini .
COPY hospital-edc-backend/scripts ./scripts
# 拷贝前端（后端静态托管）
COPY hospital-edc-frontend ./hospital-edc-frontend

# 知情同意扫描件上传目录（正式部署应挂载卷持久化）
RUN mkdir -p /app/uploads
VOLUME ["/app/uploads"]

EXPOSE 8000

# PORT 由各实例 .env 提供（compose env_file 注入），默认 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
