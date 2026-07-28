"""One-click local GPT-SoVITS bootstrap for Apple Silicon macOS."""

from __future__ import annotations

import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.request import Request, urlopen

import certifi


_REPOSITORY = "https://github.com/RVC-Boss/GPT-SoVITS.git"
_TAG = "20250606v2pro"
_COMMIT = "d7c2210da8c013e81a94bfc7b811a477c99fd506"
_PYTHON_VERSION = "3.10.20"
_MODEL_BASE = (
    "https://www.modelscope.cn/models/"
    "XXXXRT/GPT-SoVITS-Pretrained/resolve/master"
)
_BASE_ARCHIVES = (
    ("pretrained_models.zip", "GPT_SoVITS"),
    ("G2PWModel.zip", "GPT_SoVITS/text"),
)


class MacOSTTSBootstrap:
    """Install only the shared GPT-SoVITS runtime and base assets."""

    def install(
        self,
        engine_root: Path,
        progress: Callable[[str], None],
    ) -> None:
        engine_root = engine_root.expanduser().resolve()
        engine_root.parent.mkdir(parents=True, exist_ok=True)
        self._install_source(engine_root, progress)
        python = self._install_python(engine_root.parent, progress)
        virtualenv = self._install_virtualenv(
            engine_root,
            engine_root.parent,
            python,
            progress,
        )
        self._install_dependencies(engine_root, virtualenv, progress)
        self._install_base_assets(engine_root, progress)
        self._configure_cpu(engine_root, progress)

    @staticmethod
    def _uv() -> Path:
        override = os.getenv("AIPET_MACOS_UV", "").strip()
        candidates = [Path(override)] if override else []
        bundle_root = getattr(sys, "_MEIPASS", "")
        if bundle_root:
            candidates.append(Path(bundle_root) / "tools" / "uv")
        if getattr(sys, "frozen", False):
            contents = Path(sys.executable).resolve().parents[1]
            candidates.extend(
                (
                    contents / "Frameworks" / "tools" / "uv",
                    contents / "Resources" / "tools" / "uv",
                )
            )
        located = shutil.which("uv")
        if located:
            candidates.append(Path(located))
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()
        raise RuntimeError(
            "The macOS installer tool is unavailable. Use the packaged DMG "
            "or install uv before running from source."
        )

    def _install_source(
        self,
        engine_root: Path,
        progress: Callable[[str], None],
    ) -> None:
        api = engine_root / "api_v2.py"
        if api.is_file():
            progress("Using the existing GPT-SoVITS source")
            return
        if engine_root.exists() and any(engine_root.iterdir()):
            raise RuntimeError(
                "The selected GPT-SoVITS directory is not empty. Choose an "
                "empty directory or remove the incomplete installation."
            )
        staging = engine_root.parent / (
            f".{engine_root.name}-install-{uuid.uuid4().hex}"
        )
        try:
            progress("Downloading GPT-SoVITS source")
            self._run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    _TAG,
                    _REPOSITORY,
                    str(staging),
                ]
            )
            actual = self._output(["git", "-C", str(staging), "rev-parse", "HEAD"])
            if actual != _COMMIT:
                raise RuntimeError(
                    "GPT-SoVITS source verification failed; the expected "
                    "release commit was not received."
                )
            if engine_root.exists():
                engine_root.rmdir()
            os.replace(staging, engine_root)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _install_python(
        self,
        root: Path,
        progress: Callable[[str], None],
    ) -> Path:
        install_root = root / ".gpt-sovits-python"
        candidates = sorted(
            install_root.glob(
                f"cpython-{_PYTHON_VERSION}-macos-aarch64-none/bin/python3.10"
            )
        )
        if candidates:
            progress("Using the installed GPT-SoVITS Python runtime")
            return candidates[0]
        progress("Installing the isolated Python runtime")
        self._run(
            [
                str(self._uv()),
                "python",
                "install",
                "--install-dir",
                str(install_root),
                _PYTHON_VERSION,
            ]
        )
        candidates = sorted(
            install_root.glob("*/bin/python3.10")
        )
        if not candidates:
            raise RuntimeError("The isolated Python runtime was not created.")
        return candidates[0]

    def _install_virtualenv(
        self,
        engine_root: Path,
        root: Path,
        python: Path,
        progress: Callable[[str], None],
    ) -> Path:
        virtualenv = root / ".gpt-sovits-venv"
        executable = virtualenv / "bin" / "python"
        if executable.is_file():
            progress("Using the existing GPT-SoVITS virtual environment")
            return executable
        progress("Creating the GPT-SoVITS virtual environment")
        self._run(
            [
                str(self._uv()),
                "venv",
                "--no-project",
                "--python",
                str(python),
                str(virtualenv),
            ],
            cwd=engine_root,
        )
        if not executable.is_file():
            raise RuntimeError("The GPT-SoVITS virtual environment was not created.")
        return executable

    def _install_dependencies(
        self,
        engine_root: Path,
        python: Path,
        progress: Callable[[str], None],
    ) -> None:
        progress("Installing GPT-SoVITS Python dependencies")
        self._run(
            [
                str(self._uv()),
                "pip",
                "install",
                "--python",
                str(python),
                "-r",
                str(engine_root / "requirements.txt"),
            ],
            cwd=engine_root,
        )

    def _install_base_assets(
        self,
        engine_root: Path,
        progress: Callable[[str], None],
    ) -> None:
        if self._base_assets_ready(engine_root):
            progress("GPT-SoVITS base assets are already installed")
            return
        progress("Downloading GPT-SoVITS base assets")
        with tempfile.TemporaryDirectory(
            prefix="aipet-gpt-sovits-",
            dir=engine_root.parent,
        ) as directory:
            temporary = Path(directory)
            urls = {
                archive: f"{_MODEL_BASE}/{archive}"
                for archive, _destination in _BASE_ARCHIVES
            }
            context = ssl.create_default_context(cafile=certifi.where())
            sizes = {
                archive: self._remote_size(url, context)
                for archive, url in urls.items()
            }
            total = (
                sum(size for size in sizes.values() if size is not None)
                if all(size is not None for size in sizes.values())
                else None
            )
            if total:
                progress(
                    "Downloading GPT-SoVITS base assets: total "
                    f"{self._format_size(total)}"
                )
            completed = 0
            for archive, destination in _BASE_ARCHIVES:
                progress(f"Downloading {archive}")
                source = temporary / archive
                self._download(
                    urls[archive],
                    source,
                    progress=progress,
                    label=archive,
                    total=sizes[archive],
                    overall_total=total,
                    overall_before=completed,
                )
                completed += sizes[archive] or 0
                progress(f"Installing {archive}")
                self._extract_zip(source, engine_root / destination)
        if not self._base_assets_ready(engine_root):
            raise RuntimeError("GPT-SoVITS base asset installation is incomplete.")

    @staticmethod
    def _base_assets_ready(engine_root: Path) -> bool:
        required = (
            "GPT_SoVITS/pretrained_models/"
            "chinese-roberta-wwm-ext-large/pytorch_model.bin",
            "GPT_SoVITS/pretrained_models/"
            "chinese-hubert-base/pytorch_model.bin",
            "GPT_SoVITS/pretrained_models/"
            "gsv-v4-pretrained/vocoder.pth",
        )
        return all((engine_root / path).is_file() for path in required)

    @staticmethod
    def _configure_cpu(engine_root: Path, progress: Callable[[str], None]) -> None:
        config = engine_root / "GPT_SoVITS/configs/tts_infer.yaml"
        if not config.is_file():
            raise RuntimeError("GPT-SoVITS inference configuration is missing.")
        content = config.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^custom:\n.*?(?=^[^ \t].*?:|\Z)", content)
        if match is None:
            raise RuntimeError("GPT-SoVITS custom inference configuration is missing.")
        custom = match.group(0)
        configured = re.sub(r"(?m)^  device:.*$", "  device: cpu", custom, count=1)
        configured = re.sub(r"(?m)^  is_half:.*$", "  is_half: false", configured, count=1)
        if configured == custom:
            progress("GPT-SoVITS is already configured for macOS CPU")
            return
        config.write_text(content[:match.start()] + configured + content[match.end():], encoding="utf-8")
        progress("Configured GPT-SoVITS for macOS CPU")

    @staticmethod
    def _download(
        url: str,
        destination: Path,
        *,
        progress: Callable[[str], None] | None = None,
        label: str = "file",
        total: int | None = None,
        overall_total: int | None = None,
        overall_before: int = 0,
    ) -> None:
        request = Request(url, headers={"User-Agent": "AIpet-Murasame"})
        context = ssl.create_default_context(cafile=certifi.where())
        if total is None:
            total = MacOSTTSBootstrap._remote_size(url, context)
        started = time.monotonic()
        last_reported = started
        downloaded = 0

        def status(now: float) -> str:
            megabytes = downloaded / 1024**2
            completed = f"{megabytes:.0f} MB"
            if total:
                total_text = MacOSTTSBootstrap._format_size(total)
                completed += f" / {total_text} ({downloaded / total:.0%})"
            if overall_total:
                overall = overall_before + downloaded
                completed += (
                    " · total "
                    f"{MacOSTTSBootstrap._format_size(overall)} / "
                    f"{MacOSTTSBootstrap._format_size(overall_total)} "
                    f"({overall / overall_total:.0%})"
                )
            speed = megabytes / max(now - started, 0.001)
            return f"Downloading {label}: {completed} ({speed:.1f} MB/s)"

        with urlopen(request, timeout=60, context=context) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if progress is not None and now - last_reported >= 1:
                    progress(status(now))
                    last_reported = now
        if progress is not None and downloaded:
            progress(status(time.monotonic()).replace("Downloading", "Downloaded", 1))

    @staticmethod
    def _remote_size(url: str, context: ssl.SSLContext) -> int | None:
        request = Request(
            url,
            headers={"User-Agent": "AIpet-Murasame", "Range": "bytes=0-0"},
        )
        try:
            with urlopen(request, timeout=20, context=context) as response:
                _, _, total = response.headers.get("Content-Range", "").rpartition("/")
                return int(total) if total.isdigit() else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _format_size(size: int) -> str:
        return (
            f"{size / 1024**3:.1f} GB"
            if size >= 1024**3
            else f"{size / 1024**2:.0f} MB"
        )

    @staticmethod
    def _extract_zip(archive: Path, destination: Path) -> None:
        with zipfile.ZipFile(archive) as contents:
            for member in contents.infolist():
                path = PurePosixPath(member.filename)
                mode = member.external_attr >> 16
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or stat.S_ISLNK(mode)
                ):
                    raise RuntimeError(
                        f"Unsafe path in GPT-SoVITS archive: {member.filename}"
                    )
            contents.extractall(destination)

    @staticmethod
    def _run(command: list[str], *, cwd: Path | None = None) -> None:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()[-2_000:]
            raise RuntimeError(
                f"GPT-SoVITS installation command failed ({result.returncode}): {detail}"
            )

    @staticmethod
    def _output(command: list[str]) -> str:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
        return result.stdout.strip()
