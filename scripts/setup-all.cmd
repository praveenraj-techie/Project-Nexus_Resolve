@echo off
setlocal

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\services\backend"
set "DASHBOARD=%ROOT%\apps\dashboard"
set "PYTHON_EXE="
set "NPM_CMD="
set "NPX_CMD="

for /f "delims=" %%I in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
if not defined PYTHON_EXE (
  where py.exe >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=py"
)
if not defined PYTHON_EXE (
  echo Python was not found on PATH. Install Python 3.11+ or add it to PATH.
  exit /b 1
)

for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM_CMD set "NPM_CMD=%%I"
if not defined NPM_CMD if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
if not defined NPM_CMD (
  echo npm was not found on PATH. Install Node.js 20+ or add npm to PATH.
  exit /b 1
)

for /f "delims=" %%I in ('where npx.cmd 2^>nul') do if not defined NPX_CMD set "NPX_CMD=%%I"
if not defined NPX_CMD if exist "C:\Program Files\nodejs\npx.cmd" set "NPX_CMD=C:\Program Files\nodejs\npx.cmd"
if not defined NPX_CMD (
  echo npx was not found on PATH. Install Node.js 20+ or add npx to PATH.
  exit /b 1
)

for %%I in ("%NPM_CMD%") do set "NODE_DIR=%%~dpI"
set "PATH=%NODE_DIR%;%PATH%"

pushd "%BACKEND%" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  if /I "%PYTHON_EXE%"=="py" (
    call py -3 -m venv .venv || exit /b
  ) else (
    call "%PYTHON_EXE%" -m venv .venv || exit /b
  )
)
call ".venv\Scripts\python.exe" -m pip install --upgrade pip || exit /b
call ".venv\Scripts\python.exe" -m pip install -e .[dev] || exit /b
popd

pushd "%DASHBOARD%" || exit /b 1
call "%NPM_CMD%" install || exit /b
call "%NPX_CMD%" playwright install chromium || exit /b
popd

echo NEXUS-RESOLVE setup complete.
