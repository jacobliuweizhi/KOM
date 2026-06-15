@echo off
setlocal
cd /d "%~dp0"

if not exist "runtime\python\python.exe" (
  echo [ERROR] Embedded Python runtime was not found.
  pause
  exit /b 1
)

if not exist "validation" mkdir "validation"
echo Running local package validation...
"%~dp0runtime\python\python.exe" "%~dp0app\backend\validation\v9_validation.py"
set "VALIDATION_EXIT=%ERRORLEVEL%"
echo.
echo Latest saved report:
type "%~dp0validation\v9_validation_report.json"
echo.
echo Report saved to validation\v9_validation_report.json
pause
exit /b %VALIDATION_EXIT%
