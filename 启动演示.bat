@echo off
REM ============================================================
REM  EDC Demo Launcher - one click to start the full demo
REM  Steps: MySQL -> Backend -> Seed demo data -> Open browser
REM  NOTE: keep this file ASCII-only with CRLF line endings,
REM        otherwise cmd.exe fails to parse it.
REM ============================================================
cd /d %~dp0

echo [1/4] Checking MySQL container...
docker ps --filter name=hospital-edc-mysql --filter status=running -q 2>nul | findstr . >nul
if errorlevel 1 (
    echo       starting hospital-edc-mysql ...
    docker start hospital-edc-mysql >nul 2>&1
    if errorlevel 1 (
        echo       [ERROR] cannot start MySQL. Is Docker Desktop running?
        pause
        exit /b 1
    )
    echo       waiting for MySQL to be ready ...
    ping -n 13 127.0.0.1 >nul
) else (
    echo       MySQL is running.
)

echo [2/4] Checking backend on port 8000...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo       starting backend server ...
    start "EDC-Backend" /min cmd /c "cd /d %~dp0hospital-edc-backend && ..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    echo       waiting for backend to boot ...
    ping -n 9 127.0.0.1 >nul
) else (
    echo       backend already running.
)

echo [3/4] Seeding demo data (idempotent, resets demo patients)...
pushd %~dp0hospital-edc-backend
..\venv\Scripts\python.exe scripts\seed_demo.py
if errorlevel 1 (
    echo       [ERROR] seed failed. Check MySQL / .env settings.
    pause
    popd
    exit /b 1
)
popd

echo [4/4] Opening browser...
start http://127.0.0.1:8000

echo.
echo ============================================================
echo  Demo is ready!
echo    Walkthrough guide : yan-shi-shou-ce.md  (demo manual)
echo    Main account      : admin / Admin@123
echo    To stop backend   : ting-zhi-yan-shi.bat
echo ============================================================
pause
