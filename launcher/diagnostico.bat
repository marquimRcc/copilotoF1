@echo off
setlocal
cd /d "%~dp0.."
py -3 -m launcher --diagnose
if errorlevel 1 pause
endlocal
