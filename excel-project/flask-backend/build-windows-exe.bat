@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Building MobiSchola for Windows
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
    echo [1/5] Creating build environment...
    !PYTHON_CMD! -m venv .build-venv
    if !errorlevel! neq 0 goto :error
)
set "BUILD_PYTHON=.build-venv\Scripts\python.exe"

echo [2/5] Installing build dependencies and Waitress production WSGI server...
"!BUILD_PYTHON!" -m pip install --upgrade pip setuptools wheel
if !errorlevel! neq 0 goto :error
"!BUILD_PYTHON!" -m pip install --upgrade -r requirements.txt pyinstaller waitress
if !errorlevel! neq 0 goto :error
"!BUILD_PYTHON!" -c "import waitress; from waitress import serve; print('Waitress production WSGI server is installed in the build environment.')"
if !errorlevel! neq 0 goto :error

echo [3/5] Creating the Windows executable...
if exist build rmdir /s /q build
if exist "dist\MobiSchola.exe" del /q "dist\MobiSchola.exe"
"!BUILD_PYTHON!" -m PyInstaller --noconfirm --clean ExcelSchools-Windows.spec
if !errorlevel! neq 0 goto :error

if not exist "dist\MobiSchola.exe" (
    echo ERROR: PyInstaller completed but the EXE was not found.
    goto :error
)

echo [4/5] Verifying Waitress is embedded in the frozen executable...
"dist\MobiSchola.exe" --verify-production-server > "dist\production-server.txt"
if !errorlevel! neq 0 goto :server_error
findstr /c:"PRODUCTION_WSGI_STATUS=embedded-and-ready" "dist\production-server.txt" >nul
if !errorlevel! neq 0 goto :server_error
type "dist\production-server.txt"

echo [5/5] Creating LAN helpers and checksum...
copy /y "setup-lan-server.bat" "dist\setup-lan-server.bat" >nul
copy /y "test-client.bat" "dist\test-client.bat" >nul
"!BUILD_PYTHON!" -c "import hashlib,pathlib; p=pathlib.Path(r'dist\MobiSchola.exe'); pathlib.Path(str(p)+'.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')"

echo.
echo Build completed successfully:
echo   %CD%\dist\MobiSchola.exe
echo   Embedded server: Waitress production WSGI
echo   LAN setup (run on the server): %CD%\dist\setup-lan-server.bat
echo   Client test (run on client devices): %CD%\dist\test-client.bat
echo.
echo Copy all three files to the offline Windows computer, then run
echo setup-lan-server.bat as Administrator on the server computer.
pause
exit /b 0

:server_error
echo.
echo ERROR: The EXE was built but the embedded Waitress production server failed verification.
echo Delete .build-venv and run this build again.
pause
exit /b 1

:error
echo.
echo ERROR: Windows executable build failed.
pause
exit /b 1
