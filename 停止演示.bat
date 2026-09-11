@echo off
REM Stop the EDC demo backend (port 8000). MySQL container is left
REM running so data is kept; stop it manually if needed:
REM   docker stop hospital-edc-mysql
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
echo Backend stopped. (MySQL left running to preserve data.)
pause
