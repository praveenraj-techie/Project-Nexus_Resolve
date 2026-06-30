@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\services\backend"
set "DASHBOARD=%ROOT%\apps\dashboard"
set "PYTHON=%BACKEND%\.venv\Scripts\python.exe"
set "NPM_CMD="

call :ensure_local_setup
if errorlevel 1 exit /b 1

for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM_CMD set "NPM_CMD=%%I"
if not defined NPM_CMD if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
if not defined NPM_CMD (
  echo npm was not found on PATH. Install Node.js 20+ or add npm to PATH.
  exit /b 1
)
for %%I in ("%NPM_CMD%") do set "NODE_DIR=%%~dpI"

pushd "!BACKEND!" || exit /b 1
call "!PYTHON!" -m pytest || exit /b
popd

set "PATH=%NODE_DIR%;%PATH%"
pushd "!DASHBOARD!" || exit /b 1
if exist "!DASHBOARD!\node_modules\.vite" rmdir /s /q "!DASHBOARD!\node_modules\.vite"
if exist "!DASHBOARD!\node_modules\.vite-temp" rmdir /s /q "!DASHBOARD!\node_modules\.vite-temp"
if exist "!DASHBOARD!\node_modules\.cache" rmdir /s /q "!DASHBOARD!\node_modules\.cache"
call "!NPM_CMD!" run lint || exit /b
call "!NPM_CMD!" run test || exit /b
call "!NPM_CMD!" run build || exit /b
popd

echo NEXUS-RESOLVE checks passed.

exit /b 0

:ensure_local_setup
if exist "!PYTHON!" (
  if exist "!DASHBOARD!\node_modules\.bin\vite.cmd" (
    exit /b 0
  )
)
echo First run setup required. Running scripts\setup-all.cmd...
call "!ROOT!\scripts\setup-all.cmd"
if errorlevel 1 (
  echo.
  echo Automatic setup failed. Install Python 3.11+ and Node.js 20+, then rerun this script.
  exit /b 1
)
exit /b 0
