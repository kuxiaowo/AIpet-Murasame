"""Assembly of the Windows platform runtime."""

from __future__ import annotations

import ctypes
import os
import re
import shutil
from pathlib import Path
from typing import Any, Sequence

from aipet.platforms.contracts import (
    ManagedArchive,
    PlatformCapabilities,
    PlatformRuntime,
)
from aipet.platforms.windows import credentials, windowing
from aipet.platforms.windows.processes import WindowsProcessPolicy


class WindowsPathPolicy:
    def user_data_dir(self, app_name: str) -> Path:
        return Path(os.getenv("APPDATA", Path.home())) / app_name

    def cache_dir(self, app_name: str) -> Path:
        base = Path(os.getenv("LOCALAPPDATA", self.user_data_dir(app_name)))
        return base / app_name / "cache"

    def default_download_root(
        self,
        app_name: str,
        project_root: Path,
    ) -> Path:
        del app_name, project_root
        return Path("C:/AIpet/models")

    def legacy_managed_tts_root(self, app_name: str) -> Path | None:
        base = Path(os.getenv("LOCALAPPDATA", self.user_data_dir(app_name)))
        return base / app_name / "models" / "tts"


class WindowsWindowIntegration:
    def configure_widget(self, widget: Any) -> None:
        from PyQt5.QtCore import Qt

        widget.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        widget.setAttribute(Qt.WA_TranslucentBackground, True)

    def topmost_available(self) -> bool:
        return windowing.native_topmost_available()

    def ensure_topmost(self, window_id: int) -> bool:
        return windowing.ensure_window_topmost(window_id)


class WindowsInputIntegration:
    def idle_seconds(self) -> float:
        class LastInputInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint),
            ]

        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(LastInputInfo)
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        milliseconds = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
        return milliseconds / 1000.0

    def create_voice_trigger(self, **kwargs: Any) -> Any:
        from aipet.platforms.windows.voice_trigger import CapslockVoiceTrigger

        return CapslockVoiceTrigger(**kwargs)


class WindowsCredentialStore:
    def protect(self, secret: str) -> str:
        return credentials.protect_secret(secret)

    def unprotect(self, token: str) -> str:
        return credentials.unprotect_secret(token)


class WindowsArchivePolicy:
    _MODEL = "FlowerCry/gpt-sovits-7z-pacakges"
    _STANDARD = ManagedArchive(
        repository=_MODEL,
        filename="GPT-SoVITS-v2pro-20250604.7z",
        size=8_185_086_602,
        sha256=(
            "bd60d0796553ff05d8568136e199c13e0dc22ebe2ed24273134e34ed6f215cd6"
        ),
    )
    _NVIDIA50 = ManagedArchive(
        repository=_MODEL,
        filename="GPT-SoVITS-v2pro-20250604-nvidia50.7z",
        size=8_835_144_925,
        sha256=(
            "97b4edcd451c42357db7e26e6c1c877ca5d85144fe97beaff6d7005d35bee008"
        ),
    )

    def seven_zip_candidates(
        self,
        project_root: Path,
        bundled_candidate: Path,
    ) -> Sequence[Path | str | None]:
        del project_root
        if bundled_candidate.is_file():
            return (bundled_candidate,)
        candidates: list[Path | str | None] = [
            *(shutil.which(name) for name in ("7z", "7zz", "7za", "7zr")),
        ]
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.getenv(variable, "").strip()
            if root:
                candidates.append(Path(root) / "7-Zip" / "7z.exe")
        return candidates

    def tts_engine_archives(self) -> Sequence[ManagedArchive]:
        return (self._STANDARD, self._NVIDIA50)

    def select_tts_engine_archive(
        self,
        gpu_names: Sequence[str],
    ) -> ManagedArchive:
        if any(
            re.search(
                r"\bGeForce\s+RTX\s*50\d{2}\b",
                name,
                flags=re.IGNORECASE,
            )
            for name in gpu_names
        ):
            return self._NVIDIA50
        return self._STANDARD


class WindowsAudioPolicy:
    _HOSTAPI_ORDER = {
        "Windows WASAPI": 0,
        "Windows DirectSound": 1,
        "MME": 2,
        "Windows WDM-KS": 3,
    }

    @staticmethod
    def _canonical_name(name: str) -> str:
        return " ".join(name.casefold().split()).rstrip(" )")

    @classmethod
    def _is_default_alias(cls, name: str) -> bool:
        normalized = cls._canonical_name(name)
        aliases = (
            "microsoft sound mapper",
            "microsoft 声音映射器",
            "primary sound capture driver",
            "主声音捕获驱动程序",
        )
        return any(alias in normalized for alias in aliases)

    def prepare_input_devices(self, devices: Sequence[Any]) -> list[Any]:
        candidates = [
            device
            for device in devices
            if not self._is_default_alias(device.name)
        ]
        non_kernel_streaming = [
            device
            for device in candidates
            if device.hostapi != "Windows WDM-KS"
        ]
        if non_kernel_streaming:
            candidates = non_kernel_streaming
        ordered = sorted(
            candidates,
            key=lambda item: (
                self._HOSTAPI_ORDER.get(item.hostapi, 99),
                item.name.casefold(),
                item.hostapi.casefold(),
                item.index,
            ),
        )
        unique: dict[str, Any] = {}
        for device in ordered:
            unique.setdefault(self._canonical_name(device.name), device)
        return sorted(
            unique.values(),
            key=lambda item: (item.name.casefold(), item.hostapi.casefold()),
        )


def create_runtime() -> PlatformRuntime:
    return PlatformRuntime(
        platform_id="windows",
        capabilities=PlatformCapabilities(
            window_topmost=True,
            global_voice_trigger=True,
            secure_credentials=True,
            log_viewer=True,
            child_process_guard=True,
            managed_archives=True,
        ),
        paths=WindowsPathPolicy(),
        windowing=WindowsWindowIntegration(),
        input=WindowsInputIntegration(),
        credentials=WindowsCredentialStore(),
        processes=WindowsProcessPolicy(),
        archives=WindowsArchivePolicy(),
        audio=WindowsAudioPolicy(),
    )
