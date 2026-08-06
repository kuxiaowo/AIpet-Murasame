from __future__ import annotations

import importlib.util
import sys


REQUIRED_MODULES = (
    "PyInstaller",
    "PyQt5",
    "av",
    "ctranslate2",
    "cv2",
    "faster_whisper",
    "modelscope_hub",
    "numpy",
    "onnxruntime",
    "paramiko",
    "pydantic",
    "pynput",
    "requests",
    "sounddevice",
)
FORBIDDEN_MODULES = (
    "accelerate",
    "bitsandbytes",
    "torch",
    "torchaudio",
    "torchvision",
    "transformers",
)


def main() -> int:
    missing = [
        name
        for name in REQUIRED_MODULES
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        print("Missing build dependencies: " + ", ".join(missing))
        return 1

    installed = [
        name
        for name in FORBIDDEN_MODULES
        if importlib.util.find_spec(name) is not None
    ]
    if installed:
        print(
            "Refusing a polluted build environment: "
            + ", ".join(installed)
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
