@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "KOM_PORT=8027"
set "KOM_HOST=127.0.0.1"
set "PY=%~dp0runtime\python\python.exe"

if not exist "%PY%" (
  echo [ERROR] Embedded Python runtime was not found.
  echo Expected: %PY%
  echo Please extract the full zip before running this launcher.
  pause
  exit /b 1
)

"%PY%" -V >nul 2>nul
if errorlevel 1 (
  echo [ERROR] The embedded Python runtime could not start on this Windows system.
  echo This package is intended for modern 64-bit Windows. On very old Windows builds, use the public web/Docker deployment instead.
  pause
  exit /b 1
)

netstat -ano | findstr /R /C:":%KOM_PORT% .*LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo Port %KOM_PORT% is already in use. Trying 8067 instead.
  set "KOM_PORT=8067"
)

set "KOM_URL=http://127.0.0.1:%KOM_PORT%/dashboard"
echo Starting KOM Clinical Workbench on %KOM_URL%
start "KOM Clinical Workbench Server" /min "%PY%" "%~dp0app\start_server.py" --port %KOM_PORT%

echo Waiting for validation API...
for /l %%i in (1,1,35) do (
  "%PY%" -c "import urllib.request,sys; url='http://127.0.0.1:%KOM_PORT%/api/v9/validate'; sys.exit(0 if urllib.request.urlopen(url, timeout=1).status==200 else 1)" >nul 2>nul
  if not errorlevel 1 goto ready
  timeout /t 1 /nobreak >nul
)

echo [WARNING] The server did not respond within 35 seconds.
echo Try opening %KOM_URL% manually. If it still fails, run Run_Validation.bat and send validation\package_integrity_report.json.
start "" "%KOM_URL%"
pause
exit /b 1

:ready
echo Server is ready.
start "" "%KOM_URL%"
exit /b 0
