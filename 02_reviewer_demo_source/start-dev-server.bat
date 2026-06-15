@echo off
cd /d "%~dp0"
echo Starting development server and opening http://127.0.0.1:5173 ...
start "" "http://127.0.0.1:5173"
call npm.cmd install
call npm.cmd run dev
