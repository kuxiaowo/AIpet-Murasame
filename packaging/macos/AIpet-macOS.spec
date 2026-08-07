# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parents[1]
icon_path = Path(os.environ["AIPET_MACOS_ICON"])
uv_path = Path(os.environ["AIPET_MACOS_UV"])
overlay_path = Path(os.environ["AIPET_MACOS_FULLSCREEN_OVERLAY"])
gpt_sovits_source = Path(os.environ["AIPET_MACOS_GPT_SOVITS_SOURCE"])
gpt_sovits_checksum = Path(os.environ["AIPET_MACOS_GPT_SOVITS_CHECKSUM"])
app_version = os.environ.get("AIPET_MACOS_VERSION", "2.0.4-macos.1")
short_version = app_version.split("-", 1)[0]

datas = [
    (str(project_root / "fgimages"), "fgimages"),
    (str(project_root / "prompt.txt"), "."),
    (str(project_root / "prompt.en.txt"), "."),
    (str(project_root / "icon.png"), "."),
    (str(project_root / "思源黑体Bold.otf"), "."),
    (str(uv_path), "tools"),
    (str(gpt_sovits_source), "tools"),
    (str(gpt_sovits_checksum), "tools"),
    (str(overlay_path), "aipet-fullscreen-overlay"),
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
        "aipet.platforms.macos.fullscreen_overlay",
        "aipet.platforms.macos.tts_bootstrap",
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
        "CFBundleShortVersionString": short_version,
        "CFBundleVersion": app_version,
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": (
            "AIpet-Murasame uses the microphone only while you hold "
            "the configured speech-input shortcut."
        ),
    },
)
