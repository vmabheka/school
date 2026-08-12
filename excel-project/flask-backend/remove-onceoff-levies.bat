@echo off
setlocal
cd /d "%~dp0"

:: ============================================================
::  Excel Schools - Remove Once-Off Levies (Textbook Levy +
::  Registration Fee) from uploaded students' invoices.
::
::  Double-click to run. Options:
::    remove-onceoff-levies.bat --dry-run   preview only
::    remove-onceoff-levies.bat --yes       skip the confirmation prompt
:: ============================================================

echo.
echo ============================================================
echo   Excel Schools - Remove Once-Off Levies
echo   (Textbook Levy + Registration Fee)
echo ============================================================
echo.
echo IMPORTANT: Stop the Excel Schools server before running this.
echo.
echo This removes the "Textbook Levy (Once-off)" and
echo "Registration Fee (Once-off)" lines from the uploaded
echo learners' invoices and stops them being billed again.
echo.
choice /c YN /m "Continue"
if errorlevel 2 (
    echo Cancelled.
    pause
    exit /b 1
)

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
%PY% remove-onceoff-levies.py %*
echo.
pause
endlocal
