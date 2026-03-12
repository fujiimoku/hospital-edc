@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set MYSQL_CONTAINER_PRIMARY=hospital-edc-mysql
set MYSQL_CONTAINER_FALLBACK=mysql
set MYSQL_CONTAINER=

echo ========================================
echo 医院 EDC 系统状态检查 (Docker 版)
echo ========================================

echo.
echo [1/3] 检查 Docker 状态...
docker info >nul 2>&1
if %errorlevel% == 0 (
    echo ✓ Docker 正在运行
) else (
    echo ❌ Docker 未运行
    echo    请启动 Docker Desktop
)

echo.
echo [2/3] 检查 MySQL 容器状态...
docker ps --filter "name=^/%MYSQL_CONTAINER_PRIMARY%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_PRIMARY%" >nul
if !errorlevel! == 0 (
    set MYSQL_CONTAINER=%MYSQL_CONTAINER_PRIMARY%
) else (
    docker ps --filter "name=^/%MYSQL_CONTAINER_FALLBACK%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_FALLBACK%" >nul
    if !errorlevel! == 0 (
        set MYSQL_CONTAINER=%MYSQL_CONTAINER_FALLBACK%
    )
)

if not "!MYSQL_CONTAINER!" == "" (
    echo ✓ MySQL 容器正在运行
    docker ps --filter "name=^/!MYSQL_CONTAINER!$" --format "容器名: {{.Names}}, 端口: {{.Ports}}, 状态: {{.Status}}"
) else (
    echo ❌ MySQL 容器未运行
    echo.
    echo 可用的 MySQL 容器：
    docker ps -a --filter "name=mysql" --format "{{.Names}} ({{.Status}})"
    echo.
    echo 启动容器：docker start %MYSQL_CONTAINER_PRIMARY%
)

echo.
echo [3/3] 检查后端服务...
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% == 0 (
    echo ✓ 后端服务正在运行
    echo    API 文档: http://localhost:8000/api/docs
) else (
    echo ❌ 后端服务未运行
    echo    请运行 start_all_docker.bat 启动服务
)

echo.
echo ========================================
echo 检查完成
echo ========================================
echo.
echo 💡 提示：
echo    - 启动系统: 运行 start_all_docker.bat
echo    - 停止系统: 运行 stop_all_docker.bat
echo    - 查看容器: docker ps -a
echo    - 查看日志: docker logs %MYSQL_CONTAINER_PRIMARY%
echo.
pause
