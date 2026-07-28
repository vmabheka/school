@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ============================================================
echo   Excel Schools - Complete Startup Script
echo   Version 2.1.0
echo ============================================================
echo.

:: ============================================
:: Step 1: Check Python Installation
:: ============================================
echo [1/4] Checking for Python installation...

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        where python3 >nul 2>nul
        if %errorlevel% neq 0 (
            echo.
            echo ERROR: Python is not installed or not in PATH.
            echo Please install Python 3.9+ from https://python.org
            echo.
            pause
            exit /b 1
        ) else (
            set PYTHON_CMD=python3
        )
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

echo Found Python: !PYTHON_CMD!
echo.

:: ============================================
:: Step 2: Install Dependencies
:: ============================================
echo [2/4] Installing required packages...

!PYTHON_CMD! -m pip install --upgrade pip --quiet

echo Installing from requirements.txt...
!PYTHON_CMD! -m pip install -r requirements.txt --quiet

if %errorlevel% neq 0 (
    echo.
    echo Installing core packages individually...
    !PYTHON_CMD! -m pip install Flask Flask-SQLAlchemy Flask-CORS Werkzeug openpyxl requests reportlab --quiet
)

echo.
echo [3/4] Verifying Flask-CORS installation...
!PYTHON_CMD! -c "import flask_cors; print('Flask-CORS OK')" 2>nul
if %errorlevel% neq 0 (
    echo Installing Flask-CORS...
    !PYTHON_CMD! -m pip install Flask-CORS --quiet
)

echo.
echo [4/4] Starting Excel Schools Flask Server...
echo.

:: ============================================
:: Step 3: Start the Server
:: ============================================
echo Starting server using START.py...
!PYTHON_CMD! START.py

if %errorlevel% neq 0 (
    echo.
    echo Trying alternative server file...
    !PYTHON_CMD! launch.py
)

if %errorlevel% neq 0 (
    echo.
    echo Trying server.py...
    !PYTHON_CMD! server.py
)

echo.
echo ============================================================
echo   Server has stopped.
echo ============================================================
pause
endlocal