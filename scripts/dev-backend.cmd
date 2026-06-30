@echo off
setlocal

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\services\backend"

pushd "%BACKEND%" || exit /b 1
call ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
popd

