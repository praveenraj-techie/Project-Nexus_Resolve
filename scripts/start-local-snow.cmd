@echo off
setlocal

set "ROOT=%~dp0.."

echo NEXUS-RESOLVE Local SNOW desk
echo URL: http://127.0.0.1:5177/apps/local-snow/
echo.
echo This serves a local ServiceNow-style synthetic mirror only.
echo It reads FastAPI state from http://127.0.0.1:8000 and performs no external side effects.
echo.

pushd "%ROOT%" || exit /b 1
python -m http.server 5177 --bind 127.0.0.1
set "RESULT=%errorlevel%"
popd
exit /b %RESULT%
