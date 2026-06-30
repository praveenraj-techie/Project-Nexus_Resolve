@echo off
setlocal

set "ROOT=%~dp0.."
set "CHECK=%ROOT%\scripts\check-live-servicenow-env.ps1"

echo NEXUS-RESOLVE one-command live ServiceNow demo
echo.
echo This command can create a real ServiceNow PDI preflight incident,
echo update it with a work note, verify lookup by incident number,
echo and then start the local live demo.
echo.
choice /C YN /N /M "Continue? [Y/N] "
if errorlevel 2 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%CHECK%"
if errorlevel 1 (
  echo.
  echo Starting guided setup...
  call "%ROOT%\scripts\configure-live-servicenow.cmd"
  if errorlevel 1 exit /b
  powershell -NoProfile -ExecutionPolicy Bypass -File "%CHECK%"
  if errorlevel 1 exit /b
)

echo.
echo Verifying real ServiceNow create, update, and lookup permission...
call "%ROOT%\scripts\verify-live-servicenow.cmd"
if errorlevel 1 exit /b

echo.
echo Starting live demo stack...
call "%ROOT%\scripts\start-live-servicenow.cmd"
exit /b
