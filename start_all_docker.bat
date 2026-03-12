@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set MYSQL_CONTAINER_PRIMARY=hospital-edc-mysql
set MYSQL_CONTAINER_FALLBACK=mysql
set MYSQL_ROOT_PASSWORD=edc123456
set MYSQL_DATABASE=hospital_edc

echo ========================================
echo 启动医院 EDC 系统 (Docker 版)
echo ========================================

echo.
echo [1/3] 检查 Docker 是否运行...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未运行
    echo.
    echo 请先启动 Docker Desktop：
    echo 1. 打开 Docker Desktop 应用
    echo 2. 等待 Docker 启动完成（底部显示 "Engine running"）
    echo 3. 然后重新运行此脚本
    echo.
    pause
    exit /b 1
)
echo ✓ Docker 正在运行

echo.
echo [2/3] 启动 MySQL 容器...

set MYSQL_CONTAINER=

docker ps --filter "name=^/%MYSQL_CONTAINER_PRIMARY%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_PRIMARY%" >nul
if !errorlevel! == 0 (
    set MYSQL_CONTAINER=%MYSQL_CONTAINER_PRIMARY%
    echo ✓ MySQL 容器已在运行: %MYSQL_CONTAINER_PRIMARY%
    goto mysql_ok
)

docker ps --filter "name=^/%MYSQL_CONTAINER_FALLBACK%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_FALLBACK%" >nul
if !errorlevel! == 0 (
    set MYSQL_CONTAINER=%MYSQL_CONTAINER_FALLBACK%
    echo ✓ MySQL 容器已在运行: %MYSQL_CONTAINER_FALLBACK%
    goto mysql_ok
)

docker ps -a --filter "name=^/%MYSQL_CONTAINER_PRIMARY%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_PRIMARY%" >nul
if !errorlevel! == 0 (
    set MYSQL_CONTAINER=%MYSQL_CONTAINER_PRIMARY%
) else (
    docker ps -a --filter "name=^/%MYSQL_CONTAINER_FALLBACK%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_FALLBACK%" >nul
    if !errorlevel! == 0 (
        set MYSQL_CONTAINER=%MYSQL_CONTAINER_FALLBACK%
    )
)

if not "!MYSQL_CONTAINER!" == "" (
    echo 启动 MySQL 容器: !MYSQL_CONTAINER!
    docker start !MYSQL_CONTAINER! >nul 2>&1

    docker ps --filter "name=^/!MYSQL_CONTAINER!$" --format "{{.Names}}" | findstr /i /c:"!MYSQL_CONTAINER!" >nul
    if !errorlevel! == 0 (
        echo ✓ MySQL 容器启动成功
        goto mysql_ok
    )

    echo ⚠ MySQL 容器启动失败，尝试自动修复并重建...
    docker logs --tail 20 !MYSQL_CONTAINER!
    docker rm -f !MYSQL_CONTAINER! >nul 2>&1
)

echo 未找到可用容器，正在创建新 MySQL 容器: %MYSQL_CONTAINER_PRIMARY%
docker run -d --name %MYSQL_CONTAINER_PRIMARY% -p 3306:3306 -e MYSQL_ROOT_PASSWORD=%MYSQL_ROOT_PASSWORD% -e MYSQL_DATABASE=%MYSQL_DATABASE% -v hospital_edc_mysql_data:/var/lib/mysql mysql:8.0 >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo ❌ MySQL 容器创建失败
    echo 请执行以下命令查看错误：
    echo docker logs %MYSQL_CONTAINER_PRIMARY%
    echo.
    pause
    exit /b 1
)

set MYSQL_CONTAINER=%MYSQL_CONTAINER_PRIMARY%
echo ✓ MySQL 容器创建成功

echo 等待 MySQL 启动...
timeout /t 5 /nobreak > nul
docker ps --filter "name=^/%MYSQL_CONTAINER_PRIMARY%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_PRIMARY%" >nul
if !errorlevel! neq 0 (
    echo.
    echo ❌ MySQL 容器未正常运行，请查看日志：
    echo docker logs %MYSQL_CONTAINER_PRIMARY%
    echo.
    pause
    exit /b 1
)

:mysql_ok
echo.
echo [3/3] 启动后端服务...
timeout /t 2 /nobreak > nul

cd /d "%~dp0hospital-edc-backend"
if not exist "start.bat" (
    echo ❌ 找不到 start.bat 文件
    echo 当前目录: %CD%
    pause
    exit /b 1
)

start "EDC Backend" cmd /k start.bat

echo.
echo ========================================
echo ✓ 系统启动完成！
echo ========================================
echo.
echo 📝 API 文档: http://localhost:8000/api/docs
echo 🌐 前端页面: 打开 hospital-edc-frontend/index.html
echo 👤 默认账号: admin / Admin@123
echo.
echo 💡 提示：
echo   - 查看 MySQL 容器状态：docker ps
echo   - 停止 MySQL 容器：docker stop %MYSQL_CONTAINER_PRIMARY%
echo   - 查看 MySQL 日志：docker logs %MYSQL_CONTAINER_PRIMARY%
echo.
echo 按任意键关闭此窗口...
pause > nul
