@echo off
setlocal enabledelayedexpansion
title MobiSchola - Client Connection Test

:: ============================================================
::  MobiSchola - Client Connection Test
:: ============================================================
::  Run this ON A CLIENT DEVICE that cannot reach the server.
::
::  Usage:
::     test-client.bat 192.168.1.25
::  or double-click and type the server's IP address when asked.
::
::  Optional:  set EXCEL_SCHOOLS_PORT=8080  before running if the
::  server uses a different port.
:: ============================================================

if "%~1"=="" (
    set /p SERVER_IP=Enter the server computer's IP address (e.g. 192.168.1.25): 
) else (
    set "SERVER_IP=%~1"
)
if not defined EXCEL_SCHOOLS_PORT set "EXCEL_SCHOOLS_PORT=5000"
if "%SERVER_IP%"=="" (
    echo ERROR: No server IP address was entered.
    pause
    exit /b 1
)

echo.
echo Testing connection to: %SERVER_IP%  (port %EXCEL_SCHOOLS_PORT%)
echo.

:: --- 1. Ping ---------------------------------------------------
echo [1/3] Ping test - does the server answer at all?
ping -n 3 -w 2000 %SERVER_IP% >nul 2>&1
set "PING_OK=%errorlevel%"
if %PING_OK% equ 0 (
    echo        SUCCESS: the server computer answered the ping.
) else (
    echo        FAILED: no ping reply. This can mean a wrong IP, a different
    echo        network, the server being off, or ping being blocked.
)
echo.

:: --- 2. TCP port test ------------------------------------------
echo [2/3] TCP port test - is the MobiSchola port open on the server?
powershell -NoProfile -Command "$r = Test-NetConnection -ComputerName '%SERVER_IP%' -Port %EXCEL_SCHOOLS_PORT% -InformationLevel Quiet -WarningAction SilentlyContinue; if ($r) { Write-Host '        SUCCESS: port %EXCEL_SCHOOLS_PORT% is OPEN on the server.' } else { Write-Host '        FAILED: port %EXCEL_SCHOOLS_PORT% is BLOCKED or unreachable.' }"
set "TCP_OK=%errorlevel%"
echo.

:: --- 3. Web test ------------------------------------------------
echo [3/3] Web test - does the MobiSchola app answer on the server?
where curl >nul 2>&1
if %errorlevel% equ 0 (
    curl -s -o nul -w "        HTTP status: %%{http_code}\n" http://%SERVER_IP%:%EXCEL_SCHOOLS_PORT%/healthz
    set "WEB_OK=!errorlevel!"
) else (
    echo        curl not found - skipping the web test.
    set "WEB_OK=0"
)
echo.
echo ============================================================
echo  RESULT GUIDE
echo ============================================================
if %PING_OK% neq 0 (
    echo  Ping failed:
    echo    - Check that you typed the correct server IP address.
    echo    - Make sure this device and the server are on the SAME network
    echo      (same Wi-Fi name or both connected to the same router by cable).
    echo    - Check the router for "AP isolation" / "client isolation" and
    echo      disable it, or connect both devices to the router by cable.
    echo    - Make sure the server computer is switched on and the server
    echo      window is still open.
)
if %TCP_OK% neq 0 (
    echo.
    echo  Port %EXCEL_SCHOOLS_PORT% blocked:
    echo    - On the SERVER computer, run  setup-lan-server.bat  as
    echo      Administrator once (it opens the Windows Firewall).
    echo    - Set the server's network profile to Private, not Public.
    echo    - Check antivirus firewalls (Avast, Kaspersky, McAfee...) for
    echo      extra blocking rules.
) else (
    echo.
    echo  Port %EXCEL_SCHOOLS_PORT% is open - the server is reachable.
)
if %WEB_OK% neq 0 (
    echo.
    echo  Web test failed:
    echo    - Look at the server window for errors (for example the port
    echo      being already in use).
) else (
    echo.
    echo  The app is answering on the server. If the browser still fails,
    echo  open  http://%SERVER_IP%:%EXCEL_SCHOOLS_PORT%  in a private/incognito
    echo  window to rule out cached pages.
)
echo.
echo ============================================================
pause
endlocal
