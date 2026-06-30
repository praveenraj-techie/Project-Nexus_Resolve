@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"

cd /d "!ROOT!" || exit /b 1

if /I "%~1"=="--dry-run" (
  call "!ROOT!start_demo.bat" --dry-run
  exit /b
)

call "!ROOT!start_demo.bat" --openai
exit /b
