@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set MYSQL_CONTAINER_PRIMARY=hospital-edc-mysql
set MYSQL_CONTAINER_FALLBACK=mysql

echo ========================================
echo 停止医院 EDC 系统 (Docker 版)
echo ========================================

echo.
echo [1/2] 停止后端服务...
taskkill /F /FI "WINDOWTITLE eq EDC Backend*" 2>nul
if %errorlevel% == 0 (
    echo ✓ 后端服务已停止
) else (
    echo ℹ 后端服务未运行或已停止
)

echo.
echo [2/2] 停止 MySQL 容器...
set FOUND_ANY=0

docker ps --filter "name=^/%MYSQL_CONTAINER_PRIMARY%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_PRIMARY%" >nul
if !errorlevel! == 0 (
    echo 停止容器: %MYSQL_CONTAINER_PRIMARY%
    docker stop %MYSQL_CONTAINER_PRIMARY% >nul 2>&1
    if !errorlevel! == 0 (
        set FOUND_ANY=1
        echo ✓ 容器已停止
    )
)

docker ps --filter "name=^/%MYSQL_CONTAINER_FALLBACK%$" --format "{{.Names}}" | findstr /i /c:"%MYSQL_CONTAINER_FALLBACK%" >nul
if !errorlevel! == 0 (
    echo 停止容器: %MYSQL_CONTAINER_FALLBACK%
    docker stop %MYSQL_CONTAINER_FALLBACK% >nul 2>&1
    if !errorlevel! == 0 (
        set FOUND_ANY=1
        echo ✓ 容器已停止
    )
)

if !FOUND_ANY! == 0 (
    echo ℹ 未检测到运行中的 MySQL 容器
)

echo.
echo ========================================
echo ✓ 系统已停止
echo ========================================
echo.
echo 💡 提示：
echo   - MySQL 容器已停止但未删除
echo   - 下次启动时会自动恢复数据
echo   - 如需完全删除容器：docker rm %MYSQL_CONTAINER_PRIMARY%
echo.
pause
