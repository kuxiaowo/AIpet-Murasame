@echo off
setlocal EnableExtensions
set "EXITCODE=0"
set "PUSHED=0"

set "ROOT=%~dp0"

pushd "%ROOT%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Unable to access script directory: %ROOT%
    set "EXITCODE=1"
    goto :finish
)
set "PUSHED=1"

set "TTS_DIR=%ROOT%GPT-SoVITS"
set "TTS_PY=%TTS_DIR%\runtime\python.exe"
set "TTS_SCRIPT=%TTS_DIR%\api_v2.py"

if not exist "%TTS_PY%" (
    echo [ERROR] Missing GPT-SoVITS interpreter: %TTS_PY%
    set "EXITCODE=1"
    goto :finish
)

if not exist "%TTS_SCRIPT%" (
    echo [ERROR] Missing GPT-SoVITS api_v2.py: %TTS_SCRIPT%
    set "EXITCODE=1"
    goto :finish
)

echo [INFO] Starting GPT-SoVITS api_v2 server...
start "GPT-SoVITS API" /D "%TTS_DIR%" "%TTS_PY%" "%TTS_SCRIPT%"

set "CONDA_BAT="
for /f "delims=" %%I in ('where conda.bat 2^>nul') do (
    set "CONDA_BAT=%%I"
    goto :conda_found
)
for /f "delims=" %%I in ('where conda 2^>nul') do (
    if /i "%%~xI"==".bat" (
        set "CONDA_BAT=%%I"
        goto :conda_found
    )
)

:conda_found
if not defined CONDA_BAT (
    echo [ERROR] Unable to locate conda.bat. Ensure Conda is installed and on PATH.
    set "EXITCODE=1"
    goto :finish
)

echo [INFO] Activating Conda environment AIpet_env...
call "%CONDA_BAT%" activate AIpet_env
if errorlevel 1 (
    echo [ERROR] Failed to activate Conda environment AIpet_env.
    set "EXITCODE=1"
    goto :finish
)

echo [INFO] Launching main.py...
python "%ROOT%main.py"
set "EXITCODE=%ERRORLEVEL%"

:finish
if "%PUSHED%"=="1" (
    popd >nul 2>&1
)
pause
endlocal & exit /b %EXITCODE%
