@echo off
cd /d "%~dp0"
set INDEX_FILE=%~dp0KOM_Interface_Screenshot_Index.html
if exist "%INDEX_FILE%" (
  start "" "%INDEX_FILE%"
  exit /b 0
)
echo Could not find KOM_Interface_Screenshot_Index.html.
pause
