@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   Excel Schools - Windows WSGI Startup
echo ============================================================
echo.

:: Gunicorn does not support Windows. This launcher installs and runs Waitress,
:: a production-quality WSGI server that supports Windows natively.
echo [1/5] Checking Python installation...
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py"
    ) else (
        echo ERROR: Python 3.9 or newer is required.
        echo Download it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)
!PYTHON_CMD! --version

 echo.
echo [2/5] Creating the isolated Python environment...
if not exist ".venv\Scripts\python.exe" (
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo ERROR: Could not create .venv.
        pause
        exit /b 1
    )
)
set "VENV_PYTHON=.venv\Scripts\python.exe"
set "WAITRESS=.venv\Scripts\waitress-serve.exe"

 echo.
echo [3/5] Installing dependencies and the Waitress WSGI server...
"!VENV_PYTHON!" -m pip install --upgrade pip setuptools wheel
if !errorlevel! neq 0 goto :install_error
"!VENV_PYTHON!" -m pip install --upgrade -r requirements.txt
if !errorlevel! neq 0 goto :install_error
if not exist "!WAITRESS!" (
    echo ERROR: Waitress was not installed correctly.
    pause
    exit /b 1
)
"!VENV_PYTHON!" -c "import waitress; print('Waitress WSGI server installed successfully.')"

 echo.
echo [4/5] Initializing/upgrading the database...
"!VENV_PYTHON!" -c "from app import app, init_db; ctx=app.app_context(); ctx.push(); init_db(); ctx.pop(); print('Database initialized successfully.')"
if !errorlevel! neq 0 (
    echo ERROR: Database initialization failed.
    pause
    exit /b 1
)

if not defined WSGI_HOST set "WSGI_HOST=0.0.0.0"
if not defined WSGI_PORT set "WSGI_PORT=5000"
 echo.
echo [5/5] Starting Waitress WSGI server...
echo Server: http://127.0.0.1:!WSGI_PORT!
if /i "!WSGI_HOST!"=="0.0.0.0" (
    echo Other devices on this network:
    for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } | ForEach-Object { '   http://' + $_.IPAddress + ':!WSGI_PORT!' }"`) do echo %%A
    echo If client devices cannot connect, run setup-lan-server.bat as
    echo Administrator once to open the Windows Firewall for port !WSGI_PORT!.
)
echo Press Ctrl+C to stop the server.
echo ============================================================
"!WAITRESS!" --host=!WSGI_HOST! --port=!WSGI_PORT! --threads=8 wsgi:app
set "SERVER_EXIT=!errorlevel!"

echo.
echo Server stopped with exit code !SERVER_EXIT!.
pause
exit /b !SERVER_EXIT!

:install_error
echo.
echo ERROR: Dependency installation failed. Check your internet connection and Python installation.
pause
exit /b 1
