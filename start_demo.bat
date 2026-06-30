@echo off
setlocal EnableExtensions EnableDelayedExpansion

if /I "%~1"=="--inner" (
  shift /1
  goto launcher_body
)

if /I "%~1"=="--dry-run" goto launcher_body
if /I "%NEXUS_DEMO_STAY_OPEN%"=="1" goto launcher_body

start "NEXUS-RESOLVE Demo Launcher" cmd /k ""%~f0" --inner %*"
exit /b 0

:launcher_body
set "ROOT=%~dp0"
set "PRODUCT=!ROOT!"
set "DEFAULT_OPENAI_API_KEY="

cd /d "!ROOT!" || exit /b 1

if /I "%~1"=="--dry-run" (
  echo Would run combined NEXUS-RESOLVE launcher.
  echo Root:    !ROOT!
  echo Product: !PRODUCT!
  echo Main menu:
  echo   1. Use offline Demo
  echo   2. Use with OpenAI Key online demo
  echo   3. Use with OpenAI + Production integrated ServiceNow ITSM tool
  echo OpenAI key menu:
  echo   1. Use built-in default OpenAI API key
  echo   2. Paste my own key for this run
  exit /b 0
)

if /I "%~1"=="--offline" goto offline_demo
if /I "%~1"=="--openai" goto openai_demo
if /I "%~1"=="--servicenow" goto servicenow_demo

if not exist "!PRODUCT!\scripts\start-demo.cmd" (
  echo ERROR: The NEXUS product scripts were not found:
  echo   !PRODUCT!
  echo.
  echo Make sure this file is in the NEXUS_RESOLVE_FINAL project root.
  echo If you opened it from inside the downloaded ZIP, extract the ZIP first,
  echo then run start_demo.bat from the extracted folder.
  pause
  exit /b 1
)

:main_menu
cls
echo ============================================================
echo NEXUS-RESOLVE COMBINED DEMO LAUNCHER
echo ============================================================
echo Root folder:    !ROOT!
echo Product folder: !PRODUCT!
echo.
echo Choose demo mode:
echo.
echo   1. Use offline Demo
echo      Note: fully local safe demo. No OpenAI API, no real ServiceNow.
echo.
echo   2. Use with OpenAI Key online demo
echo      Note: proves real OpenAI API usage, then opens demo SNOW/local tabs.
echo      No production ITSM tool is required.
echo.
echo   3. Use with OpenAI + Production integrated ServiceNow ITSM tool
echo      Note: requires your ServiceNow Developer/PDI instance URL,
echo      username, and password. If you do not have those, use option 1 or 2.
echo.
choice /C 123 /N /M "Select option [1/2/3]: "
set "DEMO_CHOICE=%errorlevel%"

if "%DEMO_CHOICE%"=="1" goto offline_demo
if "%DEMO_CHOICE%"=="2" goto openai_demo
if "%DEMO_CHOICE%"=="3" goto servicenow_demo
goto main_menu

:offline_demo
echo.
echo ============================================================
echo MODE 1: OFFLINE DEMO
echo ============================================================
echo This runs the safe local fallback demo and opens all judge tabs.
echo.
call :ensure_local_setup
if errorlevel 1 goto failed
call :run_root_check
call :start_offline_stack
if errorlevel 1 goto failed
call :open_tabs
call :ready "Offline demo is ready. Everything is local/demo SNOW only."
exit /b 0

:openai_demo
echo.
echo ============================================================
echo MODE 2: OPENAI KEY ONLINE DEMO
echo ============================================================
echo This proves real OpenAI API usage first.
echo Then it opens the safe demo SNOW/local judge stack.
echo Real ServiceNow is not required for this mode.
echo.
call :choose_openai_key
if errorlevel 1 goto failed
call :ensure_local_setup
if errorlevel 1 goto failed
call :verify_openai
if errorlevel 1 goto failed
call :run_root_check
call :start_offline_stack
if errorlevel 1 goto failed
call :open_tabs
call :ready "OpenAI proof passed. Browser tabs use demo SNOW/local stack."
exit /b 0

:servicenow_demo
echo.
echo ============================================================
echo MODE 3: OPENAI + PRODUCTION SERVICENOW ITSM
echo ============================================================
echo This mode needs:
echo   - OpenAI API key
echo   - ServiceNow Developer/PDI instance URL, for example:
echo     https://dev123456.service-now.com
echo   - ServiceNow username and password
echo.
choice /C YN /N /M "Do you have ServiceNow Developer/PDI credentials now? [Y/N] "
if errorlevel 2 (
  echo.
  echo Use option 1 for offline demo or option 2 for OpenAI-only demo SNOW.
  pause
  goto main_menu
)
call :choose_openai_key
if errorlevel 1 goto failed
call :ensure_local_setup
if errorlevel 1 goto failed
call :run_root_check
echo.
echo Starting ServiceNow guided setup and live verifier.
echo If the setup asks for OpenAI API key, press Enter to keep the key
echo selected in this launcher.
echo.
cd /d "!PRODUCT!" || exit /b 1
call "!PRODUCT!\scripts\live-servicenow-demo.cmd"
if errorlevel 1 goto failed
call :open_tabs
call :ready "OpenAI + ServiceNow ITSM demo is ready."
exit /b 0

:choose_openai_key
if not defined OPENAI_MODEL set "OPENAI_MODEL=gpt-5.5"
echo Choose OpenAI API key source:
echo.
echo   1. Use built-in default OpenAI API key
echo   2. Paste my own key for this run ^(hidden input^)
echo.
choice /C 12 /N /M "Select option [1/2]: "
set "KEY_CHOICE=%errorlevel%"
if "%KEY_CHOICE%"=="1" (
  if not defined DEFAULT_OPENAI_API_KEY (
    echo.
    echo Built-in default OpenAI API key is not configured in this GitHub copy.
    echo Choose option 2 and paste your OpenAI API key for this run.
    pause
    goto choose_openai_key
  )
  set "OPENAI_API_KEY=%DEFAULT_OPENAI_API_KEY%"
  exit /b 0
)
if "%KEY_CHOICE%"=="2" (
  call :read_hidden_key
  if errorlevel 1 exit /b 1
  exit /b 0
)
exit /b 1

:read_hidden_key
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$secret = Read-Host 'OPENAI_API_KEY' -AsSecureString; $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret); try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }"`) do set "OPENAI_API_KEY=%%A"
if not defined OPENAI_API_KEY (
  echo OPENAI_API_KEY is empty.
  pause
  exit /b 1
)
exit /b 0

:ensure_local_setup
echo.
echo Checking local first-run setup...
if exist "!PRODUCT!\services\backend\.venv\Scripts\python.exe" (
  if exist "!PRODUCT!\apps\dashboard\node_modules\.bin\vite.cmd" (
    echo Local Python environment and dashboard packages are ready.
    exit /b 0
  )
)
echo First run detected. Installing local project dependencies now.
echo This creates services\backend\.venv and apps\dashboard\node_modules.
echo It can take a few minutes on a new machine.
echo.
if not exist "!PRODUCT!\scripts\setup-all.cmd" (
  echo ERROR: setup-all.cmd was not found under:
  echo   !PRODUCT!\scripts
  echo.
  echo If you opened this from inside the downloaded ZIP, extract the ZIP first,
  echo then run start_demo.bat from the extracted folder.
  pause
  exit /b 1
)
cd /d "!PRODUCT!" || exit /b 1
call "!PRODUCT!\scripts\setup-all.cmd"
if errorlevel 1 (
  echo.
  echo ERROR: Automatic first-run setup failed.
  echo Install Python 3.11+ and Node.js 20+, then rerun start_demo.bat.
  pause
  exit /b 1
)
echo First-run setup completed.
exit /b 0

:verify_openai
echo.
echo Verifying real OpenAI workflow...
cd /d "!PRODUCT!" || exit /b 1
call "!PRODUCT!\scripts\verify-live-openai.cmd"
if errorlevel 1 (
  echo.
  echo ERROR: OpenAI API verification failed.
  echo The judge tabs were not opened because the live API proof did not pass.
  pause
  exit /b 1
)
echo OpenAI API verification passed.
exit /b 0

:run_root_check
echo.
echo Running NEXUS product check script...
cd /d "!ROOT!" || exit /b 1
if exist "!ROOT!scripts\check-all.cmd" (
  call "!ROOT!scripts\check-all.cmd"
  if errorlevel 1 (
    echo.
    echo WARNING: Product check reported a problem.
    echo Continuing is not recommended for judging.
    echo.
  )
) else (
  echo Product check script not found. Skipping.
)
exit /b 0

:start_offline_stack
echo.
echo Starting NEXUS-RESOLVE demo SNOW/local stack...
cd /d "!PRODUCT!" || exit /b 1
call "!PRODUCT!\scripts\start-demo.cmd"
if errorlevel 1 (
  echo.
  echo ERROR: NEXUS-RESOLVE demo startup failed.
  echo Check the message above, then rerun this launcher.
  pause
  exit /b 1
)
exit /b 0

:open_tabs
echo.
echo Opening judge browser tabs...
start "" "http://localhost:5173/"
start "" "http://localhost:5173/#/incident/disk-space"
start "" "http://127.0.0.1:5177/apps/local-snow/"
start "" "http://127.0.0.1:5174/apps/deep-dive/#both"
start "" "http://127.0.0.1:8000/api/health"
exit /b 0

:ready
echo.
echo ============================================================
echo READY FOR JUDGES
echo ============================================================
echo %~1
echo.
echo Correct pages:
echo   All issues dashboard: http://localhost:5173/
echo   Disk-space demo:      http://localhost:5173/#/incident/disk-space
echo   Local SNOW:           http://127.0.0.1:5177/apps/local-snow/
echo   Deep Dive:            http://127.0.0.1:5174/apps/deep-dive/#both
echo.
echo Keep this window open while presenting.
pause
exit /b 0

:failed
echo.
echo Demo launcher stopped because a required step failed.
pause
exit /b 1
