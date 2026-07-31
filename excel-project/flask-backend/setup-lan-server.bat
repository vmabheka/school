@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: This file is copied next to ExcelSchools-Offline.exe by the build script.
set "APP_EXE=%~dp0ExcelSchools-Offline.exe"
if not exist "%APP_EXE%" set "APP_EXE=%~dp0dist\ExcelSchools-Offline.exe"
if not exist "%APP_EXE%" (
    echo ERROR: ExcelSchools-Offline.exe was not found next to this script or in dist.
    pause
    exit /b 1
)
if not defined EXCEL_SCHOOLS_PORT set "EXCEL_SCHOOLS_PORT=5000"

:: Request elevation because adding a Windows Firewall rule requires admin.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator permission to configure Windows Firewall...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Configuring a Private-network firewall rule for TCP port %EXCEL_SCHOOLS_PORT%...
netsh advfirewall firewall delete rule name="Excel Schools LAN Server" >nul 2>&1
netsh advfirewall firewall add rule name="Excel Schools LAN Server" dir=in action=allow protocol=TCP localport=%EXCEL_SCHOOLS_PORT% program="%APP_EXE%" profile=private enable=yes
if %errorlevel% neq 0 (
    echo ERROR: The firewall rule could not be created.
    pause
    exit /b 1
)

echo.
echo Network addresses for client devices:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*'} | ForEach-Object { Write-Host ('  http://' + $_.IPAddress + ':%EXCEL_SCHOOLS_PORT%') }"
echo.
echo IMPORTANT:
echo   1. Set this computer's network profile to Private.
echo   2. Keep this computer awake and connected to the router.
echo   3. Other devices must use one of the addresses shown above.
echo   4. Do not run a separate EXE/database on the client devices.
echo.
echo Starting the central Excel Schools server...
"%APP_EXE%" --host 0.0.0.0 --port %EXCEL_SCHOOLS_PORT%
endlocal
