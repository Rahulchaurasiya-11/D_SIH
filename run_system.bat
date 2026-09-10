@echo off
TITLE Legal Metrology Compliance System - SIH 2026 (PS 26034)
color 0B

echo ===============================================================================
echo   LEGAL METROLOGY COMPLIANCE SYSTEM
echo   Packaged Commodities Rules, 2011  ^|  SIH 2026 - PS 26034
echo ===============================================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH. Install Python 3.10+.
    pause
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not on PATH. Install Node.js 18+.
    pause
    exit /b 1
)

:: A missing .env is fine - the app then uses the local JSON store, no database needed.
if not exist "%~dp0backend\.env" (
    echo [SETUP] No backend\.env found. Copying .env.example ...
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
    echo [SETUP] Leaving MONGODB_URI blank runs on the local JSON store.
    echo.
)

echo [1/3] Running the compliance test suite ...
cd /d "%~dp0backend"
python -m pytest -q
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Tests reported a failure. Review the output above before demoing.
    echo.
)

echo.
echo [2/3] Starting the API on http://localhost:8000 ...
start "Legal Metrology API" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [3/3] Starting the web app on http://localhost:5173 ...
start "Legal Metrology Web" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ===============================================================================
echo   Web app   : http://localhost:5173
echo   API docs  : http://localhost:8000/docs
echo   Health    : http://localhost:8000/api/v1/health
echo.
echo   First run? Register an account - the first one becomes the administrator.
echo   Want demo data? Run:  cd backend ^&^& python scripts\seed_demo.py
echo ===============================================================================
echo.
pause
