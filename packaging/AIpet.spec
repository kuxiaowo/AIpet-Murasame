# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parent
build_variant = os.environ.get("AIPET_BUILD_VARIANT", "standard").strip()
if build_variant not in {"standard", "with-cuda"}:
    raise SystemExit(
        "AIPET_BUILD_VARIANT must be 'standard' or 'with-cuda'."
    )

app_name = "AIpet-with-cuda" if build_variant == "with-cuda" else "AIpet"
cublas_dll_names = ("cublas64_12.dll", "cublasLt64_12.dll")
cudnn_dll_names = (
    "cudnn64_9.dll",
    "cudnn_adv64_9.dll",
    "cudnn_cnn64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
    "cudnn_graph64_9.dll",
    "cudnn_heuristic64_9.dll",
    "cudnn_ops64_9.dll",
)
nvrtc_dll_names = ("nvrtc64_120_0.dll",)
binaries = []
if build_variant == "with-cuda":
    cublas_dll_directory = Path(
        os.environ.get("AIPET_CUDA_DLL_DIR", "")
    )
    cudnn_dll_directory = Path(
        os.environ.get("AIPET_CUDNN_DLL_DIR", "")
    )
    nvrtc_dll_directory = Path(
        os.environ.get("AIPET_CUDA_NVRTC_DLL_DIR", "")
    )
    cuda_dll_paths = [
        *(cublas_dll_directory / name for name in cublas_dll_names),
        *(cudnn_dll_directory / name for name in cudnn_dll_names),
        *(nvrtc_dll_directory / name for name in nvrtc_dll_names),
        *nvrtc_dll_directory.glob("nvrtc-builtins64_*.dll"),
    ]
    missing_cuda_dlls = [
        str(path) for path in cuda_dll_paths if not path.is_file()
    ]
    if missing_cuda_dlls:
        raise SystemExit(
            "CUDA build is missing required DLLs: "
            f"{', '.join(missing_cuda_dlls)}"
        )
    binaries.extend(
        (str(path), ".")
        for path in cuda_dll_paths
    )

datas = [
    (str(project_root / "fgimages"), "fgimages"),
    (str(project_root / "prompt.txt"), "."),
    (str(project_root / "prompt.en.txt"), "."),
    (str(project_root / "icon.png"), "."),
    (str(project_root / "思源黑体Bold.otf"), "."),
    (
        str(
            project_root
            / "packaging"
            / "vendor"
            / "7zip"
            / "7zr.exe"
        ),
        "packaging/vendor/7zip",
    ),
    (
        str(
            project_root
            / "packaging"
            / "vendor"
            / "7zip"
            / "README.md"
        ),
        "packaging/vendor/7zip",
    ),
]
datas += collect_data_files("faster_whisper")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "aipet.platforms.windows.runtime",
        "aipet.platforms.windows.windowing",
        "aipet.platforms.windows.credentials",
        "aipet.platforms.windows.processes",
        "aipet.platforms.windows.voice_trigger",
        "aipet.platforms.windows.log_viewer",
    ],
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

# PyQt5 bundles an outdated MSVC runtime under Qt5/bin while Conda provides a
# current, backward-compatible copy at the application root. Keeping both lets
# the Windows loader select Qt's old MSVCP140.dll for CTranslate2, which can
# crash during CUDA error handling. Retain only the root runtime DLLs.
msvc_runtime_names = {
    "msvcp140.dll",
    "msvcp140_1.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
}
a.binaries[:] = [
    entry
    for entry in a.binaries
    if not (
        str(entry[0]).replace("\\", "/").lower().startswith(
            "pyqt5/qt5/bin/"
        )
        and Path(entry[0]).name.lower() in msvc_runtime_names
    )
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=app_name,
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
