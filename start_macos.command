#!/bin/zsh

set -e

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

PYTHON_BIN="$(command -v python3.10 || command -v python3)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "需要 Python 3.10 或更高版本。"
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "当前 Python 版本过低，需要 Python 3.10 或更高版本。"
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "正在创建 macOS Python 环境…"
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements-voice.txt
fi

SOURCE="native_overlay/murasame_overlay.m"
BINARY=".native_overlay/murasame_overlay"
if [[ ! -x "$BINARY" || "$SOURCE" -nt "$BINARY" ]]; then
  if ! command -v clang >/dev/null; then
    echo "缺少 Xcode Command Line Tools，请先运行：xcode-select --install"
    exit 1
  fi
  mkdir -p .native_overlay
  echo "正在编译 macOS 全屏兼容组件…"
  clang -fobjc-arc -framework Cocoa -framework CoreGraphics \
    "$SOURCE" -o "$BINARY"
fi

exec .venv/bin/python main.py
