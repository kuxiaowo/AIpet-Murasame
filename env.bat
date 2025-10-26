@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "ENV_NAME=AIpet_env"
set "PY_VER=3.10"
set "TORCH_URL=https://download.pytorch.org/whl/cu130"

echo ==============================================
echo [AIpet 安装脚本] Conda 环境初始化
echo ==============================================

rem 检查 conda 是否可用
where conda >nul 2>&1 || (
    echo [错误] 未找到 Conda，请在 Anaconda Prompt 中运行此脚本。
    pause
    exit /b 1
)

rem 检查环境是否存在
set "ENV_EXISTS=false"
for /f "delims=" %%A in ('conda env list --json ^| findstr /I "\"%ENV_NAME%\""') do set "ENV_EXISTS=true"

if "%ENV_EXISTS%"=="true" (
    echo [提示] 环境 "%ENV_NAME%" 已存在。
    choice /M "是否删除此环境并重新创建？"
    if errorlevel 2 (
        echo [跳过] 保留原有环境。
        goto install_packages
    ) else (
        echo [信息] 正在删除旧环境...
        call conda remove -y -n "%ENV_NAME%" --all
    )
)

echo [信息] 正在创建新环境 "%ENV_NAME%"（Python %PY_VER%）...
call conda create -y -n "%ENV_NAME%" python=%PY_VER%
if errorlevel 1 goto fail

:install_packages
echo [信息] 正在激活环境 "%ENV_NAME%"...
call conda activate "%ENV_NAME%"
if errorlevel 1 goto fail

echo [信息] 正在安装 PyTorch（CUDA 13.0）...
pip install torch torchvision --index-url %TORCH_URL%
if errorlevel 1 goto fail

echo [信息] 正在安装项目依赖...
if exist "%~dp0requirements.txt" (
    pip install -r "%~dp0requirements.txt"
) else (
    echo [警告] 未找到 requirements.txt，跳过此步骤。
)
if errorlevel 1 goto fail

echo [信息] 检查并执行 download.py ...
if exist "%~dp0download.py" (
    echo [执行] 正在运行 download.py，请稍候...
    python "%~dp0download.py"
    if errorlevel 1 (
        echo [警告] download.py 执行过程中出现问题，请检查日志。
    ) else (
        echo [成功] download.py 执行完成。
    )
) else (
    echo [提示] 未找到 download.py，跳过此步骤。
)

echo.
echo [成功] 环境 "%ENV_NAME%" 已全部配置完毕！
pause
exit /b 0

:fail
echo [失败] 安装过程中出现错误。
pause
exit /b 1
