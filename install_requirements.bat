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

set "VENV_DIR=%cd%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Creating project virtual environment:
    echo %VENV_DIR%
    echo.

    where py >nul 2>nul
    if not errorlevel 1 (
        py -3.10 -m venv "%VENV_DIR%"
        if errorlevel 1 py -3 -m venv "%VENV_DIR%"
    )

    if not exist "%VENV_PY%" (
        where python >nul 2>nul
        if not errorlevel 1 (
            python -m venv "%VENV_DIR%"
        )
    )
)

if not exist "%VENV_PY%" (
    echo Python was not found or the virtual environment could not be created.
    echo Install Python 3.10+ and ensure the py launcher or python.exe is available.
    echo.
    pause
    exit /b 1
)

echo Installing Python requirements into:
echo %VENV_DIR%
echo.

call "%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    echo.
    pause
    exit /b 1
)

where nvidia-smi >nul 2>nul
if not errorlevel 1 (
    echo NVIDIA GPU detected. Installing CUDA-enabled PyTorch wheels.
    echo.
    call "%VENV_PY%" -m pip install --upgrade --force-reinstall torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
    if errorlevel 1 (
        echo Failed to install CUDA-enabled PyTorch wheels.
        echo.
        pause
        exit /b 1
    )
)

call "%VENV_PY%" -m pip install --upgrade -r requirements.txt
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Requirements installed successfully.
    echo Run start.pyw again to launch from the project virtual environment.
) else (
    echo Requirements install failed with exit code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%
