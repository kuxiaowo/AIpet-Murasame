#!/bin/zsh

set -e

PROJECT_ROOT="${0:A:h}"
ENGINE_ROOT="$PROJECT_ROOT/models/tts/GPT-SoVITS"
RUNTIME_ROOT="${AIPET_TTS_RUNTIME_DIR:-$HOME/.local/share/AIpet-Murasame/gpt-sovits}"
CONDA_ROOT="$RUNTIME_ROOT/miniforge3"
ENV_ROOT="$RUNTIME_ROOT/env"
MINIFORGE="$RUNTIME_ROOT/Miniforge3-MacOSX-arm64.sh"
MINIFORGE_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "此 macOS 安装脚本面向 Apple Silicon（arm64）。"
  exit 1
fi

if [[ ! -f "$ENGINE_ROOT/api_v2.py" ]]; then
  echo "正在下载 GPT-SoVITS 官方源码…"
  mkdir -p "$ENGINE_ROOT"
  git clone https://github.com/RVC-Boss/GPT-SoVITS.git "$ENGINE_ROOT"
fi

if [[ ! -x "$CONDA_ROOT/bin/conda" ]]; then
  echo "正在下载用户目录内的 Miniforge…"
  mkdir -p "$RUNTIME_ROOT"
  curl -L --fail --retry 3 "$MINIFORGE_URL" -o "$MINIFORGE"
  bash "$MINIFORGE" -b -p "$CONDA_ROOT"
fi

source "$CONDA_ROOT/etc/profile.d/conda.sh"
if [[ ! -x "$ENV_ROOT/bin/python" ]]; then
  echo "正在创建 GPT-SoVITS 环境…"
  conda create -y -p "$ENV_ROOT" python=3.10
fi
conda activate "$ENV_ROOT"

echo "正在准备下载工具和 GPT-SoVITS 依赖…"
conda install -y -c conda-forge wget
cd "$ENGINE_ROOT"
WORKFLOW=true bash install.sh --device CPU --source ModelScope
python -m pip install torchcodec

echo ""
echo "GPT-SoVITS 安装完成。"
echo "引擎目录：$ENGINE_ROOT"
echo "Python 环境：$ENV_ROOT/bin/python"
echo "请回到桌宠设置，点击“下载角色语音模型”，然后启动本地 TTS。"
read -r "?按回车关闭此窗口："
