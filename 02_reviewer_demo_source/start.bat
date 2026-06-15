@echo off
cd /d "%~dp0"
set INTERFACE_FILE=%~dp0KOM_Reviewer_Interface_Single_File.html
if exist "%INTERFACE_FILE%" (
  echo Opening KOM Reviewer Interface single-file version...
  start "" "%INTERFACE_FILE%"
  exit /b 0
)

set FALLBACK_FILE=%~dp0index.html
if exist "%FALLBACK_FILE%" (
  echo Opening KOM Reviewer Interface index.html...
  start "" "%FALLBACK_FILE%"
  exit /b 0
)

echo Could not find KOM_Reviewer_Interface_Single_File.html or index.html.
pause
