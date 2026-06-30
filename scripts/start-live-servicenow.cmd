@echo off
setlocal

set "ROOT=%~dp0.."
set "ENV_FILE=%ROOT%\.env"
set "ENV_TEMPLATE=%ROOT%\.env.example"
set "CHECK=%ROOT%\scripts\check-live-servicenow-env.ps1"

if exist "%ENV_FILE%" goto check_env
copy "%ENV_TEMPLATE%" "%ENV_FILE%" >nul
echo Created %ENV_FILE% from .env.example.
call :offer_setup
if "%SETUP_STATUS%"=="skipped" exit /b 2
if errorlevel 1 exit /b 2

:check_env
powershell -NoProfile -ExecutionPolicy Bypass -File "%CHECK%"
if not errorlevel 1 goto start_stack
call :offer_setup
if "%SETUP_STATUS%"=="skipped" exit /b 2
if errorlevel 1 exit /b 2
powershell -NoProfile -ExecutionPolicy Bypass -File "%CHECK%"
if errorlevel 1 exit /b 2

:start_stack
echo Optional preflight before judging:
echo   scripts\verify-live-servicenow.cmd
echo   scripts\verify-live-servicenow-run.cmd
echo.
set "NEXUS_FORCE_BACKEND_RESTART=1"
call "%ROOT%\scripts\start-demo.cmd"

exit /b

:offer_setup
set "SETUP_STATUS="
echo.
echo Live ServiceNow/OpenAI settings are incomplete.
echo Run guided setup now? This writes only to local .env.
choice /C YN /N /M "Run scripts\configure-live-servicenow.cmd? [Y/N] "
if errorlevel 2 (
  set "SETUP_STATUS=skipped"
  echo Setup skipped. Run scripts\configure-live-servicenow.cmd when ready.
  exit /b 2
)
call "%ROOT%\scripts\configure-live-servicenow.cmd"
exit /b
