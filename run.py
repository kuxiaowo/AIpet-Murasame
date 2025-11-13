import platform
import subprocess
import sys
import os
import json
import time
from tool.config import get_config
def log(msg, level="INFO"):
    levels = {
        "INFO": "[AIpet]",
        "WARN": "⚠️ [警告]",
        "ERROR": "❌ [错误]",
        "SUCCESS": "✅ [成功]",
    }
    prefix = levels.get(level, "[AIpet]")
    print(f"{prefix} {msg}")

def check_hardware():
    """检测操作系统与显卡兼容性（支持 Windows + NVIDIA GPU 或 CPU）"""
    system = platform.system()
    log(f"检测到系统: {system}")

    # Step 1️⃣ 检查系统类型
    if system != "Windows":
        log("当前系统不受支持：仅支持 Windows 设备运行。", "ERROR")
        log("如果你是 macOS 或 Linux 用户，请使用云端版本或 Docker 环境。", "INFO")
        sys.exit(1)

    # Step 2️⃣ 检测显卡信息（使用 PowerShell 替代 wmic）
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
            ],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        gpu_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        gpu_name = ", ".join(gpu_lines) if gpu_lines else "未知"
        log(f"检测到显卡: {gpu_name}")
    except Exception as e:
        log(f"无法获取显卡信息: {e}", "WARN")
        gpu_name = "未知"

    # Step 3️⃣ 判断显卡类型
    gpu_lower = gpu_name.lower()
    if "nvidia" not in gpu_lower:
        # 如果未找到NVIDIA显卡，允许使用CPU模式
        if any(bad in gpu_lower for bad in ("amd", "radeon", "intel", "iris", "arc")):
            log("当前显卡不受支持：仅支持 NVIDIA 显卡。", "ERROR")
            log("请使用带 NVIDIA GPU 的电脑，或切换到云端模式。", "INFO")
            sys.exit(1)
        else:
            log("未检测到 NVIDIA 显卡，系统将运行在 CPU 模式。", "INFO")
            # 继续执行，允许使用CPU
            return "cpu"

    log("系统兼容性检测通过：Windows + NVIDIA 显卡", "SUCCESS")
    return "nvidia"

def check_python():
    """检测 Python 版本是否满足 ≥ 3.10"""
    version_info = sys.version_info
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    log(f"检测到 Python 版本: {current_version}")

    # 检查版本
    if version_info < (3, 10):
        log("当前 Python 版本过低，Murasame 桌宠运行需要 Python ≥ 3.10。", "ERROR")
        sys.exit(1)
    else:
        log("Python 版本满足要求 (≥ 3.10)", "SUCCESS")

def install_requirements():
    """自动安装 requirements.txt 中的依赖"""
    req_path = "requirements.txt"

    # Step 1️⃣ 检查文件是否存在
    if not os.path.exists(req_path):
        log("未找到 requirements.txt，跳过依赖安装。", "WARN")
        return

    # Step 2️⃣ 执行安装命令
    log("正在安装依赖，请稍候...")
    try:
        subprocess.run(
            ["python","-m", "pip", "install", "--upgrade", "pip"],
            check=True
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path, "--upgrade", "--no-warn-script-location"],
            check=True
        )
        log("所有依赖安装完成。", "SUCCESS")
    except subprocess.CalledProcessError:
        log("依赖安装失败！请检查网络或 pip 源设置。", "ERROR")
        log("你可以尝试手动运行以下命令：", "INFO")
        log(f"    {sys.executable} -m pip install -r {req_path}", "INFO")
        sys.exit(1)

def setup_runtime_and_pytorch(config_path="config.json"):
    # Step 1️⃣ 判断配置文件
    if not os.path.exists(config_path):
        log("未找到 config.json，默认进入 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        model_type = cfg.get("model_type", "deepseek").lower()
        log(f"读取配置: model_type = {model_type}")
    except Exception as e:
        log(f"无法解析 config.json: {e}")
        log("默认进入 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    # Step 2️⃣ 判断模式
    if model_type not in ("local", "deepseek", "qwen"):
        log(f"未识别的 model_type: {model_type}，默认视为 DeepSeek 云端模式。", "WARN")
        return "deepseek"

    if model_type == "deepseek":
        log("检测到 DeepSeek 云端模式，跳过 PyTorch 安装。")
        return "deepseek"
    elif model_type == "qwen":
        log("检测到 Qwen 云端模式，跳过 PyTorch 安装。")
        return "qwen"

    log("检测到本地运行模式。")

    # 如果是CPU模式，直接跳过PyTorch安装
    if check_hardware() == "cpu":
        log("检测到 CPU 模式，跳过 PyTorch 安装。", "INFO")
        return "cpu"

    # Step 3️⃣ 检测 CUDA 环境
    cuda_version = None
    driver_version = None
    try:
        # 调用 nvidia-smi 获取原始输出
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True, text=True, encoding="gbk", check=True
        )
        output = result.stdout

        import re
        driver_match = re.search(r"Driver Version:\s*([\d\.]+)", output)
        cuda_match = re.search(r"CUDA Version:\s*([\d\.]+)", output)

        if driver_match:
            driver_version = driver_match.group(1)
        if cuda_match:
            cuda_version = cuda_match.group(1)

        if cuda_version:
            log(f"检测到 CUDA 环境: 驱动 {driver_version or '未知'}，CUDA {cuda_version}")
        else:
            log("未检测到 CUDA 版本信息，可能未正确安装显卡驱动或驱动版本过旧。", "WARN")

    except FileNotFoundError:
        log("未检测到 nvidia-smi，请确认已安装 NVIDIA 驱动。", "ERROR")
    except subprocess.CalledProcessError as e:
        log(f"执行 nvidia-smi 失败: {e}", "ERROR")
    except Exception as e:
        log(f"检测 CUDA 版本时出错: {e}", "WARN")

    if not cuda_version:
        log("未检测到 CUDA，将使用 CPU 模式。", "WARN")

    # Step 4️⃣ 选择正确的 PyTorch 安装源
    if not cuda_version:
        torch_url = "https://download.pytorch.org/whl/cpu"
        log("未检测到 CUDA，安装 CPU 版本 PyTorch。")
    elif cuda_version.startswith("13"):
        torch_url = "https://download.pytorch.org/whl/cu130"
        log("检测到 CUDA 13.x，将安装 cu130 版本。")
    elif cuda_version.startswith("12"):
        torch_url = "https://download.pytorch.org/whl/cu128"
        log("检测到 CUDA 12.x，将安装 cu128 版本。")
    elif cuda_version.startswith("11"):
        torch_url = "https://download.pytorch.org/whl/cu128"
        log("检测到 CUDA 11.x，将安装 cu128 版本。")
    else:
        torch_url = "https://download.pytorch.org/whl/cpu"
        log(f"未识别的 CUDA 版本 {cuda_version}，将安装 CPU 版本。", "WARN")

    # Step 5️⃣ 检查 PyTorch 是否已安装
    try:
        import torch
        installed_version = torch.__version__
        torch_cuda_version = torch.version.cuda or "CPU"
        log(f"已检测到 PyTorch {installed_version} (CUDA {torch_cuda_version})", "SUCCESS")

        # 检查版本匹配情况
        mismatch = False
        if torch_cuda_version == "CPU" and cuda_version:  # 系统有 CUDA，但 torch 是 CPU 版
            mismatch = True
            log(f"检测到系统 CUDA {cuda_version}，但已安装的 PyTorch 为 CPU 版。", "WARN")
        elif cuda_version and not torch_cuda_version.startswith(cuda_version.split('.')[0]):
            mismatch = True
            log(f"当前 CUDA 版本为 {cuda_version}，但 PyTorch 构建基于 CUDA {torch_cuda_version}。", "WARN")

        if mismatch:
            log("开始安装与当前 CUDA 版本匹配的 PyTorch...", "INFO")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-U",
                "torch", "torchvision", "torchaudio",
                "--index-url", torch_url,
                "--no-warn-script-location"
            ], check=True)
            import torch
            log("已安装与当前 CUDA 匹配的 PyTorch 版本。", "SUCCESS")
            log("⚠️⚠️请关闭并重新运行程序，以加载新的 PyTorch 版本。⚠️⚠️", "INFO")
            sys.exit(0)

    except ImportError:
        log("未检测到 PyTorch，开始安装...", "INFO")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "torch", "torchvision", "torchaudio",
                "--index-url", torch_url,
                "--no-warn-script-location"
            ], check=True)
            import torch
            log(f"成功安装 PyTorch {torch.__version__} (CUDA {torch.version.cuda or 'CPU'})", "SUCCESS")
        except subprocess.CalledProcessError:
            log("PyTorch 安装失败！请检查网络或 CUDA 环境。", "ERROR")
            sys.exit(1)

    return model_type

def run_download():
    script_path = os.path.abspath(r".\download.py")

    if not os.path.exists(script_path):
        log(f"未找到文件: {script_path}", "ERROR")
        return

    log(f"正在运行模型下载脚本：{script_path}", "INFO")
    try:
        subprocess.run(["python", "download.py"],)
        log("模型下载完成。", "SUCCESS")
    except subprocess.CalledProcessError as e:
        log(f"下载脚本运行失败: {e}", "ERROR")

def start_tts_api():
    """使用 GPT-SoVITS 自带解释器在新的控制台窗口中启动 TTS API。"""
    tts_type = get_config("./config.json")["tts_type"]
    if tts_type == "local":
        log("检测到 tts_type = local", "INFO")
        python_path = os.path.abspath(r".\GPT-SoVITS\runtime\python.exe")
        script_path = os.path.abspath(r".\GPT-SoVITS\api_v2.py")
        work_dir = r".\GPT-SoVITS"

        if not os.path.exists(os.path.join(work_dir, script_path)):
            log(f"未找到脚本: {os.path.join(work_dir, script_path)}", "ERROR")
            return None

        log(f"使用解释器 {python_path} 启动 TTS 服务（新控制台）...")

        try:
            proc = subprocess.Popen(
                [python_path, script_path],
                cwd=work_dir,
                creationflags=(0x00000010 if os.name == "nt" else 0)
            )
            time.sleep(5)
            log("TTS 服务已在新控制台启动。")
            return proc
        except Exception as e:
            log(f"启动 TTS 失败: {e}", "ERROR")
            return None
    elif tts_type == "cloud":
        try:
            proc = subprocess.Popen(
                  ["ssh", "aipet", "bash", "run.sh"],
                  creationflags=(0x00000010 if os.name == "nt" else 0)
            )
            time.sleep(5)
            log("TTS 服务已在新控制台启动。")
            return proc
        except Exception as e:
            log(f"启动 TTS 失败: {e}", "ERROR")
            return None

def run_main():
    script_path = os.path.abspath(r".\main.py")

    if not os.path.exists(script_path):
        log(f"未找到文件: {script_path}", "ERROR")
        return

    log(f"正在运行主程序：{script_path}", "INFO")
    try:
        subprocess.run(["python", "main.py"],)
    except subprocess.CalledProcessError as e:
        log(f"桌宠启动失败: {e}", "ERROR")

if __name__ == "__main__":
    check_hardware()
    check_python()
    install_requirements()
    setup_runtime_and_pytorch()
    run_download()
    start_tts_api()
    run_main()
