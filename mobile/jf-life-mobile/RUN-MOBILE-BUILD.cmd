@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN-MOBILE-BUILD.ps1" %*
exit /b %errorlevel%
