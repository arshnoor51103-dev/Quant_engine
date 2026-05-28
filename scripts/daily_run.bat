@echo off
setlocal

set PYTHONUTF8=1
cd /d "%~dp0.."

call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate .venv
    exit /b 1
)

python scripts\daily_run.py > "logs\bat.log" 2>&1
exit /b %errorlevel%
