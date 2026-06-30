@echo off
setlocal

set "ROOT=%~dp0.."
set "DASHBOARD=%ROOT%\apps\dashboard"
set "NPM_CMD="

for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM_CMD set "NPM_CMD=%%I"
if not defined NPM_CMD if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
if not defined NPM_CMD (
  echo npm was not found on PATH. Install Node.js 20+ or add npm to PATH.
  exit /b 1
)
for %%I in ("%NPM_CMD%") do set "NODE_DIR=%%~dpI"

set "PATH=%NODE_DIR%;%PATH%"
pushd "%DASHBOARD%" || exit /b 1
call "%NPM_CMD%" run dev -- --host 127.0.0.1 --port 5173
popd
