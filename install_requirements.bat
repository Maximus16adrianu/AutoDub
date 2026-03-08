@echo off
setlocal

cd /d "%~dp0"

if not exist "requirements.txt" (
    echo requirements.txt was not found in:
    echo %cd%
    echo.
    pause
    exit /b 1
)

set "PY_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo Python was not found on PATH.
    echo Install Python 3.10+ and ensure the launcher or python.exe is available.
    echo.
    pause
    exit /b 1
)

echo Installing Python requirements from:
echo %cd%\requirements.txt
echo.

call %PY_CMD% -m pip install -r requirements.txt
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Requirements installed successfully.
) else (
    echo Requirements install failed with exit code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%
