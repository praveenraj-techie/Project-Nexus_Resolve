@echo off
setlocal

if "%NEXUS_SKIP_OPEN_TABS%"=="1" (
  echo NEXUS_SKIP_OPEN_TABS=1, not opening browser tabs.
  exit /b 0
)

echo Opening NEXUS-RESOLVE judge tabs...
start "" "http://localhost:5173/"
start "" "http://localhost:5173/#/incident/disk-space"
start "" "http://127.0.0.1:5177/apps/local-snow/"
start "" "http://127.0.0.1:5174/apps/deep-dive/#both"
start "" "http://127.0.0.1:8000/api/health"

exit /b 0
