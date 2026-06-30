@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
set "BACKEND=%ROOT%\services\backend"
set "DASHBOARD=%ROOT%\apps\dashboard"
set "PYTHON=%BACKEND%\.venv\Scripts\python.exe"
set "NPM_CMD="

echo NEXUS-RESOLVE local judge demo launcher
echo Root: !ROOT!
echo.

call :ensure_local_setup
if errorlevel 1 exit /b 1

for /f "delims=" %%I in ('where npm.cmd 2^>nul') do if not defined NPM_CMD set "NPM_CMD=%%I"
if not defined NPM_CMD if exist "C:\Program Files\nodejs\npm.cmd" set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
if not defined NPM_CMD (
  echo npm was not found on PATH. Install Node.js 20+ or add npm to PATH.
  exit /b 1
)
for %%I in ("%NPM_CMD%") do set "NODE_DIR=%%~dpI"
set "PATH=%NODE_DIR%;%PATH%"

call :ensure_backend
call :ensure_dashboard
call :ensure_deep_dive
call :ensure_local_snow

echo.
echo Waiting for health checks...
call :wait_url "Backend health" "http://127.0.0.1:8000/api/health"
call :wait_url "Dashboard" "http://localhost:5173"
call :wait_url "Deep dive" "http://127.0.0.1:5174/apps/deep-dive/"
call :wait_url "Local SNOW" "http://127.0.0.1:5177/apps/local-snow/"

echo.
echo Open these URLs:
echo   Dashboard:  http://localhost:5173/#/incident/disk-space
echo   Local SNOW: http://127.0.0.1:5177/apps/local-snow/
echo   Deep dive:  http://127.0.0.1:5174/apps/deep-dive/#both
echo   Backend:    http://127.0.0.1:8000/api/health
echo   E2E proof:  scripts\run-e2e.cmd
echo.
echo This launcher forces APP_MODE=mock for the no-ServiceNow judge demo.
echo Use scripts\live-servicenow-demo.cmd only when real PDI credentials are configured.
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

:wait_url
powershell -NoProfile -ExecutionPolicy Bypass -Command "$label='%~1'; $url='%~2'; for ($i = 0; $i -lt 25; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2; Write-Host ($label + ': ' + $r.StatusCode); exit 0 } catch { Start-Sleep -Seconds 1 } }; Write-Host ($label + ': not reachable yet')"
exit /b 0

:port_in_use
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
exit /b

:backend_current
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2; if ($r.Content -like '*audit-report.pdf*' -and $r.Content -like '*servicenow/incidents/{incident_number}*' -and $r.Content -like '*itsm-twin*' -and $r.Content -like '*comms/{draft_id}/approve*' -and $r.Content -like '*local-snow/latest*') { exit 0 } } catch {}; exit 1"
exit /b

:backend_is_nexus
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($h.service -eq 'nexus-resolve') { exit 0 } } catch {}; exit 1"
exit /b

:dashboard_current
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:5173/#/incident/disk-space' -TimeoutSec 2; if ($r.Content -like '*<title>NEXUS-RESOLVE</title>*') { exit 0 } } catch {}; exit 1"
exit /b

:deep_dive_current
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5174/apps/deep-dive/' -TimeoutSec 2; if ($r.Content -like '*Judge Console*') { exit 0 } } catch {}; exit 1"
exit /b

:local_snow_current
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5177/apps/local-snow/' -TimeoutSec 2; if ($r.Content -like '*NEXUS Local SNOW Desk*') { exit 0 } } catch {}; exit 1"
exit /b

:loopback_port_in_use
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
exit /b

:stop_port
powershell -NoProfile -ExecutionPolicy Bypass -Command "$connections = Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue; foreach ($connection in $connections) { Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue }"
exit /b 0

:ensure_backend
if "%NEXUS_FORCE_BACKEND_RESTART%"=="1" (
  echo NEXUS_FORCE_BACKEND_RESTART=1. Restarting backend so current .env is loaded.
  call :stop_port 8000
  timeout /t 2 /nobreak >nul
  goto start_backend
)
call :port_in_use 8000
if errorlevel 1 goto start_backend
call :backend_current
if not errorlevel 1 (
  echo Port 8000 already has a listener. Reusing existing backend.
  exit /b 0
)
call :backend_is_nexus
if errorlevel 1 (
  echo Port 8000 is in use, but it is not the current NEXUS backend. Stop that process or free port 8000.
  exit /b 1
)
echo Port 8000 has a stale NEXUS backend. Restarting it to load the current API.
call :stop_port 8000
timeout /t 2 /nobreak >nul
:start_backend
echo Starting backend on 8000...
start "NEXUS backend" /D "!BACKEND!" cmd /k "set APP_MODE=mock&& .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
exit /b 0

:ensure_dashboard
call :port_in_use 5173
if "%errorlevel%"=="0" (
  call :dashboard_current
  if not errorlevel 1 (
    echo Port 5173 already has the current NEXUS dashboard. Reusing it.
    exit /b 0
  )
  echo Port 5173 has a different app. Restarting it for the NEXUS dashboard.
  call :stop_port 5173
  timeout /t 2 /nobreak >nul
)
echo Starting dashboard on 5173...
start "NEXUS dashboard" /D "!DASHBOARD!" cmd /k ""!NPM_CMD!" run dev -- --host localhost --port 5173"
exit /b 0

:ensure_deep_dive
call :deep_dive_current
if not errorlevel 1 (
  echo Port 5174 already has a listener. Reusing existing deep-dive server.
  exit /b 0
)
call :loopback_port_in_use 5174
if not errorlevel 1 (
  echo Port 5174 on 127.0.0.1 is in use, but it is not serving the deep-dive page. Stop that process or free port 5174.
  exit /b 1
)
echo Starting deep-dive page on 5174...
start "NEXUS deep dive" /D "!ROOT!" cmd /k ""!PYTHON!" -m http.server 5174 --bind 127.0.0.1"
exit /b 0

:ensure_local_snow
call :local_snow_current
if not errorlevel 1 (
  echo Port 5177 already has a listener. Reusing existing Local SNOW server.
  exit /b 0
)
call :loopback_port_in_use 5177
if not errorlevel 1 (
  echo Port 5177 on 127.0.0.1 is in use, but it is not serving the Local SNOW page. Stop that process or free port 5177.
  exit /b 1
)
echo Starting Local SNOW page on 5177...
start "NEXUS Local SNOW" /D "!ROOT!" cmd /k ""!PYTHON!" -m http.server 5177 --bind 127.0.0.1"
exit /b 0
