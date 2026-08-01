@echo off
title Meat Products of India — Desktop App
color 0A
cls

echo ============================================================
echo   Meat Products of India — Billing ^& Inventory App
echo   Desktop Application Mode
echo ============================================================
echo.

:: Verify Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    pause
    exit /b 1
)

:: Install / update dependencies (silently)
echo [1/2] Checking dependencies...
python -m pip install -q -r "%~dp0requirements.txt"
python -m pip install -q pywebview

:: Launch the desktop app
echo [2/2] Launching Desktop Window...
echo.
python "%~dp0run_desktop.py"

pause
