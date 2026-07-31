@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Building Excel Schools Offline for Windows
 echo ============================================================

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo ERROR: Install Python 3.9 or newer from https://python.org
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

if not exist ".build-venv\Scripts\python.exe" (
    echo [1/4] Creating build environment...
    !PYTHON_CMD! -m venv .build-venv
    if !errorlevel! neq 0 goto :error
)
set "BUILD_PYTHON=.build-venv\Scripts\python.exe"

echo [2/4] Installing build dependencies...
"!BUILD_PYTHON!" -m pip install --upgrade pip setuptools wheel
if !errorlevel! neq 0 goto :error
"!BUILD_PYTHON!" -m pip install --upgrade -r requirements.txt pyinstaller
if !errorlevel! neq 0 goto :error

echo [3/4] Creating the Windows executable...
if exist build rmdir /s /q build
if exist "dist\ExcelSchools-Offline.exe" del /q "dist\ExcelSchools-Offline.exe"
"!BUILD_PYTHON!" -m PyInstaller --noconfirm --clean ExcelSchools-Windows.spec
if !errorlevel! neq 0 goto :error

if not exist "dist\ExcelSchools-Offline.exe" (
    echo ERROR: PyInstaller completed but the EXE was not found.
    goto :error
)

echo [4/4] Creating checksum...
"!BUILD_PYTHON!" -c "import hashlib,pathlib; p=pathlib.Path(r'dist\ExcelSchools-Offline.exe'); pathlib.Path(str(p)+'.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')"

echo.
echo Build completed successfully:
echo   %CD%\dist\ExcelSchools-Offline.exe
echo.
echo Copy the EXE to the offline Windows computer and double-click it.
pause
exit /b 0

:error
echo.
echo ERROR: Windows executable build failed.
pause
exit /b 1
