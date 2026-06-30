@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\services\backend\.venv\Scripts\python.exe"

if not exist "!PYTHON!" (
  echo First run setup required. Running scripts\setup-all.cmd...
  call "!ROOT!\scripts\setup-all.cmd"
  if errorlevel 1 (
    echo.
    echo Automatic setup failed. Install Python 3.11+ and Node.js 20+, then rerun this script.
    exit /b 1
  )
)

call "!PYTHON!" "!ROOT!\scripts\verify-live-openai.py"
exit /b
