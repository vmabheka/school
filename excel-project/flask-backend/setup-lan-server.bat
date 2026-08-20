@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ============================================================
::  MobiSchola - Central LAN Server Setup (run on the SERVER)
:: ============================================================
::  Opens the Windows Firewall for the server port and starts the
::  offline server so every device on the same network can feed
::  data into this one computer.
::
::  Usage:  double-click this file (it will ask for Administrator)
::  Options (set before running):
::    EXCEL_SCHOOLS_PORT=8080            other port
::    EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE=1   also allow Public networks
:: ============================================================

set "APP_EXE=%~dp0MobiSchola.exe"
if not exist "%APP_EXE%" set "APP_EXE=%~dp0dist\MobiSchola.exe"
if not exist "%APP_EXE%" (
    echo ERROR: MobiSchola.exe was not found next to this script or in dist.
    pause
    exit /b 1
)

if not defined EXCEL_SCHOOLS_PORT set "EXCEL_SCHOOLS_PORT=5000"
if not defined EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE set "EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE=0"

:: --- Elevate: firewall changes need administrator rights ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator permission to configure Windows Firewall...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo  MobiSchola - Central LAN Server Setup
echo ============================================================
echo.

:: --- 1. Windows Firewall --------------------------------------
:: Port-based rule (no "program=" filter): the PyInstaller one-file EXE
:: listens from a child process in a temporary folder, so a rule scoped
:: to the EXE path never matches and clients are silently blocked.
:: The rule covers Private + Domain networks; Public is optional because
:: Public networks are treated as untrusted by Windows.
set "PROFILES=private,domain"
if /i "%EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE%"=="1" set "PROFILES=private,domain,public"

echo [1/4] Opening Windows Firewall for TCP port %EXCEL_SCHOOLS_PORT%  (%PROFILES%)...
netsh advfirewall firewall delete rule name="MobiSchola LAN Server" >nul 2>&1
netsh advfirewall firewall add rule name="MobiSchola LAN Server" dir=in action=allow protocol=TCP localport=%EXCEL_SCHOOLS_PORT% profile=%PROFILES% enable=yes
if %errorlevel% neq 0 (
    echo ERROR: Could not create the firewall rule. Run this script as administrator.
    pause
    exit /b 1
)
echo        OK: Firewall rule "MobiSchola LAN Server" - TCP %EXCEL_SCHOOLS_PORT% IN (allow).

:: --- 2. Network profile check ----------------------------------
echo.
echo [2/4] Checking the network profile...
powershell -NoProfile -Command ^
  "$p = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -ne 'Disconnected' }; " ^
  "if (-not $p) { Write-Host '   No active network connection found.' } else { " ^
  "  $p | ForEach-Object { Write-Host ('   Network: ' + $_.Name + '   Profile: ' + $_.NetworkCategory) }; " ^
  "  if ($p.NetworkCategory -contains 'Public') { " ^
  "    Write-Host '   WARNING: a network is set to Public - Windows blocks sharing on Public networks.'; " ^
  "    Write-Host '   Change it to Private in Settings, Network and Internet, your connection, Private.'; " ^
  "    Write-Host '   Or rerun with EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE=1.' } }"

:: --- 3. Permanent server address --------------------------------
:: A name-based address (http://<COMPUTERNAME>:port) never changes even if
:: the IP does, so client devices always use the same URL.
echo.
echo [3/5] Permanent server address:
echo    Computer name: %COMPUTERNAME%
echo    Permanent address: http://%COMPUTERNAME%:%EXCEL_SCHOOLS_PORT%
echo.
if /i not "%COMPUTERNAME%"=="MOBISCHOLA-SERVER" (
    choice /c YN /m "Rename this computer to MOBISCHOLA-SERVER so the permanent address is always http://MOBISCHOLA-SERVER:%EXCEL_SCHOOLS_PORT%"
    if errorlevel 2 (
        echo    Skipped - keeping the current computer name.
    ) else (
        echo    Renaming computer to MOBISCHOLA-SERVER (a restart will be needed)...
        wmic computersystem where "name='%COMPUTERNAME%'" call rename name="MOBISCHOLA-SERVER" >nul 2>&1
        if !errorlevel! equ 0 (
            echo    OK: renamed. After the next restart use http://MOBISCHOLA-SERVER:%EXCEL_SCHOOLS_PORT%
        ) else (
            echo    WARNING: could not rename automatically - rename it in
            echo    Settings ^> System ^> About ^> Rename this PC.
        )
    )
)

:: Desktop shortcut to the permanent portal address
set "SHORTCUT=%USERPROFILE%\Desktop\MobiSchola Portal.url"
(
    echo [InternetShortcut]
    echo URL=http://%COMPUTERNAME%:%EXCEL_SCHOOLS_PORT%
    echo IconIndex=0
) > "%SHORTCUT%"
echo    Desktop shortcut created: MobiSchola Portal.url
echo.

:: --- 4. LAN addresses -------------------------------------------
echo [4/5] Addresses that client devices must open:
set "ADDRESSES="
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } | ForEach-Object { 'http://' + $_.IPAddress + ':%EXCEL_SCHOOLS_PORT%' }"`) do (
    echo    %%A
    set "ADDRESSES=!ADDRESSES! %%A"
)
if defined ADDRESSES (
    echo.
    echo    The addresses above were copied to the clipboard - paste them to your clients.
    echo %ADDRESSES% | clip
)

:: --- 5. Start the server and self-check --------------------------
:: The server runs independently of a browser on this machine; clients
:: connect with their own browsers.
echo.
echo [5/5] Starting the central MobiSchola server (no browser opens on this machine)...
start "MobiSchola LAN Server" "%APP_EXE%" --lan --host 0.0.0.0 --port %EXCEL_SCHOOLS_PORT%
echo        Waiting for the server to start...
powershell -NoProfile -Command "Start-Sleep -Seconds 6; $ok = Test-NetConnection -ComputerName 127.0.0.1 -Port %EXCEL_SCHOOLS_PORT% -InformationLevel Quiet -WarningAction SilentlyContinue; if ($ok) { Write-Host '   SUCCESS: the server is listening on port %EXCEL_SCHOOLS_PORT%.' } else { Write-Host '   WARNING: the server did not answer - check the server window for errors.' }"

echo.
echo Done. Client devices on this network can now open the addresses above.
echo The permanent address is shown in the server window and saved to
echo server-address.txt in the data folder.
echo If a client still cannot connect, go to the CLIENT computer and run:
echo     test-client.bat ^<server IP^>
echo   e.g.  test-client.bat 192.168.1.25
echo.
endlocal
