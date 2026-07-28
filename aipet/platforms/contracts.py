from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence


class PlatformNotImplementedError(RuntimeError):
    """Raised when a platform adapter has not implemented a required ability."""


class CredentialError(RuntimeError):
    """Raised when the active platform cannot securely store a credential."""


class ChildProcessGuard(Protocol):
    def assign(self, process: Any) -> None: ...

    def close(self) -> None: ...


class PathPolicy(Protocol):
    def user_data_dir(self, app_name: str) -> Path: ...

    def cache_dir(self, app_name: str) -> Path: ...

    def default_download_root(
        self,
        app_name: str,
        project_root: Path,
    ) -> Path: ...

    def legacy_managed_tts_root(self, app_name: str) -> Path | None: ...


class WindowIntegration(Protocol):
    def configure_widget(self, widget: Any) -> None: ...

    def topmost_available(self) -> bool: ...

    def ensure_topmost(self, window_id: int) -> bool: ...


class InputIntegration(Protocol):
    def idle_seconds(self) -> float: ...

    def voice_trigger_shortcut(self) -> str: ...

    def create_voice_trigger(self, **kwargs: Any) -> Any: ...


class CredentialStore(Protocol):
    def protect(self, secret: str) -> str: ...

    def unprotect(self, token: str) -> str: ...


class ProcessPolicy(Protocol):
    def hidden_subprocess_options(self) -> dict[str, Any]: ...

    def new_console_subprocess_options(self) -> dict[str, Any]: ...

    def console_python_executable(self, executable: str) -> str: ...

    def create_child_process_guard(self) -> ChildProcessGuard: ...

    def runtime_python_candidates(
        self,
        engine_root: Path,
    ) -> Sequence[Path]: ...

    def log_viewer_command(
        self,
        executable: str,
        log_directory: Path,
        parent_process_id: int,
        *,
        frozen: bool,
        viewer_script: Path,
    ) -> list[str]: ...

    def follow_log_viewer(
        self,
        log_directory: Path,
        parent_process_id: int,
    ) -> None: ...


class AudioPolicy(Protocol):
    def prepare_input_devices(self, devices: Sequence[Any]) -> list[Any]: ...


@dataclass(frozen=True)
class PlatformCapabilities:
    window_topmost: bool
    global_voice_trigger: bool
    secure_credentials: bool
    log_viewer: bool
    child_process_guard: bool
    managed_archives: bool


@dataclass(frozen=True)
class ManagedArchive:
    repository: str
    filename: str
    size: int
    sha256: str


class ArchivePolicy(Protocol):
    def seven_zip_candidates(
        self,
        project_root: Path,
        bundled_candidate: Path,
    ) -> Sequence[Path | str | None]: ...

    def tts_engine_archives(self) -> Sequence[ManagedArchive]: ...

    def select_tts_engine_archive(
        self,
        gpu_names: Sequence[str],
    ) -> ManagedArchive: ...


@dataclass(frozen=True)
class PlatformRuntime:
    platform_id: str
    capabilities: PlatformCapabilities
    paths: PathPolicy
    windowing: WindowIntegration
    input: InputIntegration
    credentials: CredentialStore
    processes: ProcessPolicy
    archives: ArchivePolicy
    audio: AudioPolicy
