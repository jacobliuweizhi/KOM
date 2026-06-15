@echo off
setlocal
cd /d "%~dp0"
set "KOM_PORT=8027"
set "KOM_URL=http://127.0.0.1:%KOM_PORT%/dashboard"

if not exist "runtime\python\python.exe" (
  echo [ERROR] Embedded Python runtime was not found.
  echo Expected: %~dp0runtime\python\python.exe
  pause
  exit /b 1
)

echo Starting KOM Clinical Workbench on %KOM_URL%
echo This package uses the embedded runtime and does not require system Python.

start "KOM Clinical Workbench Server" /min "%~dp0runtime\python\python.exe" "%~dp0app\start_server.py" --port %KOM_PORT%

echo Waiting for the local server...
for /l %%i in (1,1,20) do (
  "%~dp0runtime\python\python.exe" -c "import urllib.request,sys; url='http://127.0.0.1:%KOM_PORT%/api/v9/validate'; sys.exit(0 if urllib.request.urlopen(url, timeout=1).status==200 else 1)" >nul 2>nul
  if not errorlevel 1 goto ready
  timeout /t 1 /nobreak >nul
)

echo [WARNING] The server did not respond within 20 seconds.
echo Please keep this window open and try opening %KOM_URL% manually.
start "" "%KOM_URL%"
pause
exit /b 1

:ready
echo Server is ready.
start "" "%KOM_URL%"
echo If you need the validation JSON, open http://127.0.0.1:%KOM_PORT%/api/v9/validate
exit /b 0
