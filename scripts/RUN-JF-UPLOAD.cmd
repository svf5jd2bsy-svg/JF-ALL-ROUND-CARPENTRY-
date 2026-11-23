@echo off
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN-JF-UPLOAD.ps1" %*
exit /b %errorlevel%
