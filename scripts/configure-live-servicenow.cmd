@echo off
setlocal

set "ROOT=%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\configure-live-servicenow.ps1"
exit /b
