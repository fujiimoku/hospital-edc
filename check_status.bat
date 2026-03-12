@echo off
chcp 65001 > nul
echo ========================================
echo 医院 EDC 系统状态检查
echo ========================================

echo.
echo [1/3] 检查 MySQL 服务状态...
sc query MySQL | find "RUNNING" >nul
if %errorlevel% == 0 (
    echo ✓ MySQL 服务正在运行
) else (
    sc query MySQL80 | find "RUNNING" >nul
    if %errorlevel% == 0 (
        echo ✓ MySQL80 服务正在运行
    ) else (
        echo ❌ MySQL 服务未运行
        echo    请运行 start_all.bat 启动服务
    )
)

echo.
echo [2/3] 检查 MySQL 连接...
mysql -u root -pedc123456 -e "SELECT 1;" 2>nul
if %errorlevel% == 0 (
    echo ✓ MySQL 连接正常
) else (
    echo ❌ MySQL 连接失败
    echo    请检查密码或数据库配置
)

echo.
echo [3/3] 检查后端服务...
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% == 0 (
    echo ✓ 后端服务正在运行
    echo    API 文档: http://localhost:8000/api/docs
) else (
    echo ❌ 后端服务未运行
    echo    请运行 start_all.bat 启动服务
)

echo.
echo ========================================
echo 检查完成
echo ========================================
echo.
echo 💡 提示：
echo    - 启动系统: 运行 start_all.bat
echo    - 停止系统: 运行 stop_all.bat
echo    - 访问文档: http://localhost:8000/api/docs
echo.
pause
