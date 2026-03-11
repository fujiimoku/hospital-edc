@echo off
echo ========================================
echo 启动前端开发服务器
echo ========================================
echo.
echo 前端将在 http://localhost:8080 启动
echo 请确保后端服务已在 http://localhost:8000 运行
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

cd /d "%~dp0"
python -m http.server 8080
