@echo off
setlocal

set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\services\backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Backend virtual environment is missing. Run scripts\setup-all.cmd first.
  exit /b 1
)

call "%PYTHON%" "%ROOT%\scripts\verify-live-servicenow-run.py"
exit /b
