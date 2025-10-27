@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ========= 可配置 =========
set "ENV_NAME=AIpet_env"
set "PY_VER=3.10"
set "TORCH_URL=https://download.pytorch.org/whl/cu130"
rem =========================

echo ==============================================
echo [AIpet 安装脚本] Conda 环境初始化
echo ==============================================

where conda >nul 2>&1 || (
    echo [错误] 未找到 Conda。
    pause
    exit /b 1
)


for /f "delims=" %%B in ('conda info --base') do set "CONDA_BASE=%%B"


set "ENV_EXISTS=false"
if exist "%CONDA_BASE%\envs\%ENV_NAME%" (
    set "ENV_EXISTS=true"
)

if "%ENV_EXISTS%"=="true" (
    echo [提示] 环境 "%ENV_NAME%" 已存在。
    echo.
    set /p "user_choice=是否删除此环境并重新创建？(Y/N): "
    if /I "%user_choice%"=="N" (
        echo [跳过] 保留原有环境。
        goto :install_packages
    ) else if /I "%user_choice%"=="Y" (
        echo [信息] 正在删除旧环境...
        call conda remove -y -n "%ENV_NAME%" --all || goto fail
    ) else (
        echo [警告] 输入无效，默认保留原有环境。
        goto :install_packages
    )
)


echo [信息] 正在创建新环境 "%ENV_NAME%"（Python %PY_VER%）...
call conda create -y -n "%ENV_NAME%" python=%PY_VER% || goto fail

:install_packages

echo [信息] 正在激活环境 "%ENV_NAME%"...
call conda activate "%ENV_NAME%" || goto fail


set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"


echo [信息] 正在安装 PyTorch（CUDA 13.0）...
python -c "import sys; print(sys.version)" 1>nul 2>nul || goto fail
pip install --upgrade pip || goto fail
pip install torch torchvision --index-url %TORCH_URL% || goto fail

echo [信息] 正在安装项目依赖...
if exist "%~dp0requirements.txt" (
    pip install -r "%~dp0requirements.txt" || goto fail
) else (
    echo [警告] 未找到 requirements.txt，跳过此步骤。
)

echo.
echo [成功] 环境 "%ENV_NAME%" 已成功安装并配置完成！
pause
exit /b 0

:fail
echo [失败] 安装过程中出现错误。
pause
exit /b 1
