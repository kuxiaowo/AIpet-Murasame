# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parents[1]
icon_path = Path(os.environ["AIPET_MACOS_ICON"])

datas = [
    (str(project_root / "fgimages"), "fgimages"),
    (str(project_root / "prompt.txt"), "."),
    (str(project_root / "icon.png"), "."),
    (str(project_root / "思源黑体Bold.otf"), "."),
]
datas += collect_data_files("faster_whisper")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "aipet.platforms.macos.runtime",
        "aipet.platforms.macos.credentials",
        "aipet.platforms.macos.voice_trigger",
        "aipet.platforms.macos.windowing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "accelerate",
        "aipet.platforms.windows",
        "bitsandbytes",
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIpet-Murasame",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=str(
        project_root / "packaging" / "macos" / "entitlements.plist"
    ),
)

app_files = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AIpet-Murasame",
)

app = BUNDLE(
    app_files,
    name="AIpet-Murasame.app",
    icon=str(icon_path),
    bundle_identifier="com.aipet.murasame",
    info_plist={
        "CFBundleDisplayName": "AIpet-Murasame",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": (
            "AIpet-Murasame uses the microphone only while you hold "
            "the configured speech-input shortcut."
        ),
    },
)
