@echo off
setlocal
cd /d "%~dp0"
set "KOM_PORT=8027"

echo Opening validation endpoint:
echo http://127.0.0.1:%KOM_PORT%/api/v9/validate
start "" "http://127.0.0.1:%KOM_PORT%/api/v9/validate"
