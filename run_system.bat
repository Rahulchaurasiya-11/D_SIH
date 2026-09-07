@echo off
TITLE Legal Metrology Compliance Auditing System - SIH 2026 Runner
color 0B

echo ===============================================================================
echo          LEGAL METROLOGY COMPLIANCE AUDITING SYSTEM (PCR 2011)
echo                   Smart India Hackathon 2026 Edition
echo ===============================================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

:: Check for Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH. Please install Node.js 18+.
    pause
    exit /b 1
)

echo [1/3] Verifying Backend Compliance Engine Unit Tests...
cd /d "%~dp0backend"
python test_engine.py
if %errorlevel% neq 0 (
    echo [WARNING] Unit test run flagged a notice. Proceeding with service startup...
)

echo.
echo [2/3] Starting FastAPI Backend on http://localhost:8000...
start "Legal Metrology Backend (FastAPI)" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [3/3] Starting React Frontend on http://localhost:5173...
start "Legal Metrology Frontend (React + Vite)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ===============================================================================
echo  SYSTEM SERVICES LAUNCHED SUCCESSFULLY!
echo  - Backend API & Swagger Docs: http://localhost:8000/docs
echo  - Frontend Compliance Dashboard: http://localhost:5173
echo ===============================================================================
echo.
pause
