@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

pushd "%REPO_ROOT%" || exit /b 1

set "ICLOUD_PATH=%USERPROFILE%\iCloudDrive\JF LIFE"
set "DRIVE_D_PATH=D:\JF LIFE"

echo Running JF LIFE link process...
echo iCloud source: "%ICLOUD_PATH%"
echo D drive source: "%DRIVE_D_PATH%"

where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul || (
    echo Python was not found. Install Python, then rerun this script.
    popd
    exit /b 1
  )
  python scripts\jf_life_link.py ^
    --source "iCloud=%ICLOUD_PATH%" ^
    --source "ExternalD=%DRIVE_D_PATH%" ^
    %*
) else (
  py -3 scripts\jf_life_link.py ^
    --source "iCloud=%ICLOUD_PATH%" ^
    --source "ExternalD=%DRIVE_D_PATH%" ^
    %*
)

set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
