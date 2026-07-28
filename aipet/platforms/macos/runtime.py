"""macOS implementations of the platform runtime contracts."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from aipet.platforms.contracts import (
    ManagedArchive,
    PlatformCapabilities,
    PlatformNotImplementedError,
    PlatformRuntime,
)
from aipet.platforms.macos.credentials import KeychainStore
from aipet.platforms.macos import windowing
from aipet.platforms.macos.tts_bootstrap import MacOSTTSBootstrap


class MacOSPathPolicy:
    def user_data_dir(self, app_name: str) -> Path:
        return Path.home() / "Library" / "Application Support" / app_name

    def cache_dir(self, app_name: str) -> Path:
        return Path.home() / "Library" / "Caches" / app_name

    def default_download_root(
        self,
        app_name: str,
        project_root: Path,
    ) -> Path:
        del app_name, project_root
        return Path.home() / "Downloads" / "AIpet" / "models"

    def legacy_managed_tts_root(self, app_name: str) -> Path | None:
        del app_name
        return None


class MacOSWindowIntegration:
    @staticmethod
    def _uses_cocoa() -> bool:
        from PyQt5.QtGui import QGuiApplication

        return QGuiApplication.platformName() == "cocoa"

    def configure_widget(self, widget: Any) -> None:
        from PyQt5.QtCore import Qt

        widget.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        widget.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        widget.setAttribute(Qt.WA_TranslucentBackground, True)
        if self._uses_cocoa():
            windowing.configure_native_window(int(widget.winId()))

    def topmost_available(self) -> bool:
        return True

    def ensure_topmost(self, window_id: int) -> bool:
        return (
            self._uses_cocoa()
            and windowing.configure_native_window(window_id)
        )


class MacOSInputIntegration:
    _IDLE_TIME = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')

    def idle_seconds(self) -> float:
        try:
            result = subprocess.run(
                ["ioreg", "-c", "IOHIDSystem"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return 0.0
        match = self._IDLE_TIME.search(result.stdout)
        return int(match.group(1)) / 1_000_000_000 if match else 0.0

    def create_voice_trigger(self, **kwargs: Any) -> Any:
        from aipet.platforms.macos.voice_trigger import OptionVVoiceTrigger

        return OptionVVoiceTrigger(**kwargs)

    def voice_trigger_shortcut(self) -> str:
        return "Option+V"


class MacOSChildProcessGuard:
    def assign(self, process: Any) -> None:
        del process

    def close(self) -> None:
        return None


class MacOSProcessPolicy:
    def hidden_subprocess_options(self) -> dict[str, Any]:
        return {}

    def new_console_subprocess_options(self) -> dict[str, Any]:
        return {}

    def console_python_executable(self, executable: str) -> str:
        return executable

    def create_child_process_guard(self) -> MacOSChildProcessGuard:
        return MacOSChildProcessGuard()

    def runtime_python_candidates(
        self,
        engine_root: Path,
    ) -> Sequence[Path]:
        return (
            engine_root / ".venv" / "bin" / "python",
            engine_root.parent / ".gpt-sovits-venv" / "bin" / "python",
            engine_root / "runtime" / "bin" / "python",
            engine_root / "bin" / "python",
            engine_root / "python",
        )

    def log_viewer_command(
        self,
        executable: str,
        log_directory: Path,
        parent_process_id: int,
        *,
        frozen: bool,
        viewer_script: Path,
    ) -> list[str]:
        del executable, parent_process_id, frozen, viewer_script
        return ["open", str(log_directory)]

    def follow_log_viewer(
        self,
        log_directory: Path,
        parent_process_id: int,
    ) -> None:
        del parent_process_id
        subprocess.run(["open", str(log_directory)], check=True)


class MacOSArchivePolicy:
    def seven_zip_candidates(
        self,
        project_root: Path,
        bundled_candidate: Path,
    ) -> Sequence[Path | str | None]:
        del project_root, bundled_candidate
        return tuple(
            candidate
            for candidate in (
                shutil.which("7zz"),
                shutil.which("7z"),
                shutil.which("7za"),
                shutil.which("7zr"),
                Path("/opt/homebrew/bin/7zz"),
                Path("/usr/local/bin/7zz"),
            )
            if candidate and Path(candidate).is_file()
        )

    def tts_engine_archives(self) -> Sequence[ManagedArchive]:
        return ()

    def select_tts_engine_archive(
        self,
        gpu_names: Sequence[str],
    ) -> ManagedArchive:
        del gpu_names
        raise PlatformNotImplementedError(
            "Managed GPT-SoVITS archives are not available on macOS yet."
        )


class MacOSAudioPolicy:
    def prepare_input_devices(self, devices: Sequence[Any]) -> list[Any]:
        return sorted(
            devices,
            key=lambda device: (
                device.name.casefold(),
                device.hostapi.casefold(),
                device.index,
            ),
        )


def create_runtime() -> PlatformRuntime:
    return PlatformRuntime(
        platform_id="macos",
        capabilities=PlatformCapabilities(
            window_topmost=True,
            global_voice_trigger=True,
            secure_credentials=True,
            log_viewer=True,
            child_process_guard=False,
            managed_archives=False,
            managed_tts_bootstrap=True,
        ),
        paths=MacOSPathPolicy(),
        windowing=MacOSWindowIntegration(),
        input=MacOSInputIntegration(),
        credentials=KeychainStore(),
        processes=MacOSProcessPolicy(),
        archives=MacOSArchivePolicy(),
        audio=MacOSAudioPolicy(),
        tts_bootstrap=MacOSTTSBootstrap(),
    )
