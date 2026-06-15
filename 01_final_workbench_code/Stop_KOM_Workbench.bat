@echo off
setlocal
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8027 ^| findstr LISTENING') do (
  echo Stopping process %%a on port 8027
  taskkill /PID %%a /F
)
echo Done.
pause
