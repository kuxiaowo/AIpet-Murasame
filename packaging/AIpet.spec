# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parent

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
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "accelerate",
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
    a.binaries,
    a.datas,
    [],
    name="AIpet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_root / "icon.ico")],
)
