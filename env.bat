@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ========= Configuration =========
set "ENV_NAME=AIpet_env"
set "PY_VER=3.10"
set "TORCH_URL=https://download.pytorch.org/whl/cu130"
rem =================================

echo ==============================================
echo [AIpet Setup Script] Conda Environment Initialization
echo ==============================================

where conda >nul 2>&1 || (
    echo [ERROR] Conda not found.
    echo Please run this script in **Anaconda Prompt**, or make sure Conda is initialized with "conda init cmd".
    pause
    exit /b 1
)

for /f "delims=" %%B in ('conda info --base') do set "CONDA_BASE=%%B"

set "ENV_EXISTS=false"
if exist "%CONDA_BASE%\envs\%ENV_NAME%" (
    set "ENV_EXISTS=true"
)

if "%ENV_EXISTS%"=="true" (
    echo [NOTICE] The environment "%ENV_NAME%" already exists.
    echo.
    set "user_choice="
    set /p "user_choice=Do you want to delete this environment and recreate it? (Y/N): "
    if /I "!user_choice!"=="N" (
        echo [SKIP] Keeping the existing environment.
        goto :install_packages
    ) else if /I "!user_choice!"=="Y" (
        echo [INFO] Removing old environment...
        call conda remove -y -n "%ENV_NAME%" --all || goto fail
    ) else (
        echo [WARNING] Invalid input, keeping the existing environment by default.
        goto :install_packages
    )
)

echo [INFO] Creating a new environment "%ENV_NAME%" (Python %PY_VER%)...
call conda create -y -n "%ENV_NAME%" python=%PY_VER% || goto fail

:install_packages
echo [INFO] Activating environment "%ENV_NAME%"...
call conda activate "%ENV_NAME%" || goto fail

set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"

echo [INFO] Installing PyTorch (CUDA 13.0)...
python -c "import sys; print(sys.version)" 1>nul 2>nul || goto fail

pip install torch torchvision --index-url %TORCH_URL% || goto fail

echo [INFO] Installing project dependencies...
if exist "%~dp0requirements.txt" (
    pip install -r "%~dp0requirements.txt" || goto fail
) else (
    echo [WARNING] requirements.txt not found, skipping this step.
)

echo [INFO] Downloading models...
if exist "%~dp0download.py" (
    python "%~dp0download.py" || goto fail
) else (
    echo [WARNING] download.py not found, skipping model download.
)

echo.
echo [SUCCESS] Environment "%ENV_NAME%" has been successfully installed and configured!
pause
exit /b 0

:fail
echo [FAILURE] An error occurred during installation.
pause
exit /b 1
