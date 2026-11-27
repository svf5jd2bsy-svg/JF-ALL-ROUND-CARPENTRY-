@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

pushd "%REPO_ROOT%" || exit /b 1

set "ICLOUD_PATH=%USERPROFILE%\iCloudDrive\JF LIFE"
set "DRIVE_D_PATH=D:\JF LIFE"
if defined JF_LIFE_ICLOUD_SOURCE set "ICLOUD_PATH=%JF_LIFE_ICLOUD_SOURCE%"
if defined JF_LIFE_DRIVE_SOURCE set "DRIVE_D_PATH=%JF_LIFE_DRIVE_SOURCE%"

echo Running JF LIFE link process...
echo iCloud source: "%ICLOUD_PATH%"
echo D drive source: "%DRIVE_D_PATH%"

set "PYTHON_EXE=py"
set "PYTHON_PREFIX=-3"
if defined JF_LIFE_PYTHON (
  if not exist "%JF_LIFE_PYTHON%" (
    echo JF_LIFE_PYTHON does not point to a Python executable.
    popd
    exit /b 1
  )
  set "PYTHON_EXE=%JF_LIFE_PYTHON%"
  set "PYTHON_PREFIX="
) else (
  where py >nul 2>nul || (
    where python >nul 2>nul || (
      echo Python was not found. Install Python, then rerun this script.
      popd
      exit /b 1
    )
    set "PYTHON_EXE=python"
    set "PYTHON_PREFIX="
  )
)
"%PYTHON_EXE%" %PYTHON_PREFIX% scripts\run_jf_life.py scripts\jf_life_link.py ^
  --source "iCloud=%ICLOUD_PATH%" ^
  --source "ExternalD=%DRIVE_D_PATH%" ^
  %*

set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
