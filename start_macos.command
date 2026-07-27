#!/bin/zsh

set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

PYTHON_BIN="$(command -v python3.10 || command -v python3)"
if [[ ! -x ".venv/bin/python" ]]; then
  echo "正在创建 Python 环境…"
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

if [[ -f "native_overlay/murasame_overlay.m" && ( ! -x ".native_overlay/murasame_overlay" || "native_overlay/murasame_overlay.m" -nt ".native_overlay/murasame_overlay" ) ]]; then
  mkdir -p .native_overlay
  echo "正在编译 macOS 全屏兼容组件…"
  clang -fobjc-arc -framework Cocoa -framework CoreGraphics \
    native_overlay/murasame_overlay.m -o .native_overlay/murasame_overlay
fi

exec .venv/bin/python main.py
