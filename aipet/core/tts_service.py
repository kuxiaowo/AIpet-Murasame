"""Shared GPT-SoVITS service orchestration."""

from __future__ import annotations

import atexit
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from aipet.core.autodl_tts import AutoDLTTSConnection
from aipet.core.config import TTSSettings, get_cache_dir
from aipet.core.credentials import CredentialError, unprotect_secret
from aipet.core.network import is_loopback_url
from aipet.core.runtime_logging import get_logger
from aipet.core.tts_assets import (
    TTSAssetState,
    locate_tts_assets,
    tts_service_is_reachable,
)
from aipet.platforms import PlatformRuntime, get_platform_runtime


ProgressCallback = Callable[[str], None]
logger = get_logger("tts-service")


class TTSServiceError(RuntimeError):
    pass


class LocalTTSServiceManager:
    """Own at most one GPT-SoVITS API process for the current AIpet process."""

    def __init__(
        self,
        platform_runtime: PlatformRuntime | None = None,
    ) -> None:
        self._platform_runtime = (
            platform_runtime or get_platform_runtime()
        )
        self._condition = threading.Condition(threading.RLock())
        self._process: subprocess.Popen[bytes] | None = None
        self._autodl_connection: AutoDLTTSConnection | None = None
        self._process_job = (
            self._platform_runtime.processes.create_child_process_guard()
        )
        self._log_file = None
        self._server_address: tuple[str, int] | None = None
        self._starting = False
        self._shutting_down = False

    def is_starting(self) -> bool:
        with self._condition:
            return self._starting

    def owns_running_process(self) -> bool:
        with self._condition:
            return self._process_is_running_locked() or (
                self._autodl_connection is not None
                and self._autodl_connection.is_active()
            )

    def ensure_running(
        self,
        settings: TTSSettings,
        *,
        state: TTSAssetState | None = None,
        progress: ProgressCallback | None = None,
        password: str = "",
    ) -> bool:
        """Ensure the selected TTS API is reachable; return True if started."""

        if settings.uses_autodl():
            return self._ensure_autodl_running(
                settings,
                progress=progress,
                password=password,
            )

        address = _local_server_address(settings.base_url)
        if tts_service_is_reachable(settings.base_url):
            logger.info("TTS 服务已在线 | %s", settings.base_url)
            return False

        deadline = time.monotonic() + settings.timeout_seconds
        with self._condition:
            if self._shutting_down:
                raise TTSServiceError("AIpet is shutting down.")
            while self._starting:
                _report(progress, "waiting_for_existing_start")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TTSServiceError(
                        "Timed out while another TTS startup was in progress."
                    )
                self._condition.wait(min(0.5, remaining))
            if tts_service_is_reachable(settings.base_url):
                return False
            if self._process_is_running_locked():
                if self._server_address != address:
                    raise TTSServiceError(
                        "AIpet already manages a TTS service on another address. "
                        "Stop it in Settings before changing the endpoint."
                    )
                raise TTSServiceError(
                    "The managed TTS process is running, but its API is not "
                    "reachable. Stop it in Settings and try again."
                )
            self._close_dead_process_locked()
            self._starting = True

        process: subprocess.Popen[bytes] | None = None
        try:
            _report(progress, "locating_engine")
            assets = state or locate_tts_assets(
                configured_engine_root=settings.engine_root,
                configured_model_dir=settings.model_dir,
            )
            if assets.engine_root is None:
                raise TTSServiceError("GPT-SoVITS directory was not found.")
            if not assets.engine_ready:
                raise TTSServiceError(
                    "GPT-SoVITS is incomplete. Download or repair the engine "
                    "before starting its API."
                )

            command, environment = _build_start_command(
                assets.engine_root,
                address,
                self._platform_runtime,
            )
            _report(progress, "starting_process")
            process = self._launch(
                command,
                environment,
                assets.engine_root,
                address,
            )
            _report(progress, "waiting_for_api")
            while time.monotonic() < deadline:
                if tts_service_is_reachable(
                    settings.base_url,
                    timeout=0.75,
                ):
                    _report(progress, "ready")
                    logger.info(
                        "TTS 服务启动完成 | %s | PID %s",
                        settings.base_url,
                        getattr(process, "pid", "unknown"),
                    )
                    return True
                exit_code = process.poll()
                if exit_code is not None:
                    detail = self._read_log_tail()
                    suffix = f"\n{detail}" if detail else ""
                    raise TTSServiceError(
                        f"GPT-SoVITS exited with code {exit_code}.{suffix}"
                    )
                time.sleep(0.35)

            detail = self._read_log_tail()
            suffix = f"\n{detail}" if detail else ""
            raise TTSServiceError(
                "Timed out waiting for the GPT-SoVITS API to become ready."
                + suffix
            )
        except Exception:
            logger.exception("TTS 服务启动失败")
            if process is not None:
                self._terminate_process(process)
            with self._condition:
                if self._process is process:
                    self._process = None
                    self._server_address = None
                    self._close_log_locked()
            raise
        finally:
            with self._condition:
                self._starting = False
                self._condition.notify_all()

    def stop(self) -> bool:
        """Stop only services and SSH sessions launched by this AIpet process."""

        with self._condition:
            process = self._process
            autodl_connection = self._autodl_connection
            self._autodl_connection = None
            if process is None and autodl_connection is None:
                self._close_log_locked()
                return False

        if process is not None:
            self._terminate_process(process)
            logger.info(
                "TTS 服务已停止 | PID %s",
                getattr(process, "pid", "unknown"),
            )
        if autodl_connection is not None:
            autodl_connection.stop()
            logger.info("AutoDL TTS SSH 会话已关闭")
        with self._condition:
            if self._process is process:
                self._process = None
                self._server_address = None
                self._close_log_locked()
            self._condition.notify_all()
        return True

    def _ensure_autodl_running(
        self,
        settings: TTSSettings,
        *,
        progress: ProgressCallback | None,
        password: str,
    ) -> bool:
        with self._condition:
            active_connection = self._autodl_connection
        if (
            active_connection is not None
            and active_connection.is_active()
            and tts_service_is_reachable(settings.base_url)
        ):
            logger.info("AutoDL TTS 服务已在线 | %s", settings.base_url)
            return False
        if tts_service_is_reachable(settings.base_url):
            raise TTSServiceError(
                "The local TTS port is occupied by a service that was not "
                "started through the current AutoDL SSH session. Stop that "
                "service or use another local port."
            )

        address = _local_server_address(settings.base_url)
        deadline = time.monotonic() + settings.timeout_seconds
        with self._condition:
            if self._shutting_down:
                raise TTSServiceError("AIpet is shutting down.")
            while self._starting:
                _report(progress, "waiting_for_existing_start")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TTSServiceError(
                        "Timed out while another TTS startup was in progress."
                    )
                self._condition.wait(min(0.5, remaining))
            if tts_service_is_reachable(settings.base_url):
                active_connection = self._autodl_connection
                if (
                    active_connection is not None
                    and active_connection.is_active()
                ):
                    return False
                raise TTSServiceError(
                    "The local TTS port is occupied by another service."
                )
            if (
                self._autodl_connection is not None
                and self._autodl_connection.is_active()
            ):
                raise TTSServiceError(
                    "The AutoDL SSH session is active, but its TTS API is not "
                    "reachable. Stop it in Settings and try again."
                )
            self._autodl_connection = None
            self._starting = True

        connection = AutoDLTTSConnection()
        try:
            clear_password = password
            if not clear_password:
                try:
                    clear_password = unprotect_secret(
                        settings.autodl_password_encrypted
                    )
                except CredentialError as exc:
                    raise TTSServiceError(str(exc)) from exc
            connection.start(
                settings.autodl_ssh_command,
                clear_password,
                settings.autodl_remote_command,
                local_address=address,
                remote_address=("127.0.0.1", 9880),
                progress=progress,
            )
            with self._condition:
                self._autodl_connection = connection

            _report(progress, "waiting_for_api")
            while time.monotonic() < deadline:
                if tts_service_is_reachable(
                    settings.base_url,
                    timeout=0.75,
                ):
                    _report(progress, "ready")
                    logger.info(
                        "AutoDL TTS 启动完成 | %s",
                        settings.base_url,
                    )
                    return True
                if not connection.is_active():
                    detail = connection.output_tail()
                    suffix = f"\n{detail}" if detail else ""
                    raise TTSServiceError(
                        "The AutoDL SSH session ended before TTS became ready."
                        + suffix
                    )
                time.sleep(0.35)

            detail = connection.output_tail()
            suffix = f"\n{detail}" if detail else ""
            raise TTSServiceError(
                "Timed out waiting for the AutoDL TTS API to become ready."
                + suffix
            )
        except Exception:
            logger.exception("AutoDL TTS 启动失败")
            connection.stop()
            with self._condition:
                if self._autodl_connection is connection:
                    self._autodl_connection = None
            raise
        finally:
            with self._condition:
                self._starting = False
                self._condition.notify_all()

    def shutdown(self) -> None:
        with self._condition:
            self._shutting_down = True
        try:
            self.stop()
        finally:
            self._process_job.close()

    def autodl_reference(
        self,
        settings: TTSSettings,
        emotion: str,
    ) -> tuple[str, str]:
        with self._condition:
            connection = self._autodl_connection
        if (
            connection is None
            or not connection.is_active()
            or not settings.uses_autodl()
        ):
            raise TTSServiceError(
                "The AutoDL SSH session is not active."
            )
        try:
            return connection.read_reference_metadata(
                settings.autodl_remote_reference_root,
                emotion,
            )
        except Exception as exc:
            raise TTSServiceError(str(exc)) from exc

    def _launch(
        self,
        command: list[str],
        environment: dict[str, str],
        engine_root: Path,
        address: tuple[str, int],
    ) -> subprocess.Popen[bytes]:
        log_path = get_cache_dir() / "logs" / "gpt-sovits-service.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("ab", buffering=0)
        log_file.write(
            (
                f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                "Starting GPT-SoVITS API\n"
            ).encode("utf-8")
        )
        kwargs = (
            self._platform_runtime.processes.hidden_subprocess_options()
        )
        try:
            process = subprocess.Popen(
                command,
                cwd=str(engine_root),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                **kwargs,
            )
        except Exception:
            log_file.close()
            raise
        try:
            self._process_job.assign(process)
        except OSError as exc:
            logger.warning(
                "无法把 TTS 子进程绑定到桌宠生命周期：%s",
                exc,
            )
        with self._condition:
            self._process = process
            self._log_file = log_file
            self._server_address = address
        logger.info(
            "TTS 子进程已创建 | PID %s | 原始日志=%s",
            getattr(process, "pid", "unknown"),
            log_path,
        )
        return process

    def _process_is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _close_dead_process_locked(self) -> None:
        if self._process is not None and self._process.poll() is not None:
            self._process = None
            self._server_address = None
            self._close_log_locked()

    def _close_log_locked(self) -> None:
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        except OSError:
            pass

    @staticmethod
    def _read_log_tail() -> str:
        path = get_cache_dir() / "logs" / "gpt-sovits-service.log"
        try:
            data = path.read_bytes()[-12_000:]
        except OSError:
            return ""
        return data.decode("utf-8", errors="replace").strip()


def _local_server_address(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or not is_loopback_url(base_url):
        raise TTSServiceError(
            "Automatic startup is available only for a local HTTP TTS endpoint."
        )
    host = parsed.hostname or "127.0.0.1"
    if host.lower() == "localhost":
        host = "127.0.0.1"
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise TTSServiceError("The TTS endpoint contains an invalid port.") from exc
    return host, port


def _build_start_command(
    engine_root: Path,
    address: tuple[str, int],
    platform_runtime: PlatformRuntime | None = None,
) -> tuple[list[str], dict[str, str]]:
    python = _locate_runtime_python(engine_root, platform_runtime)
    api_script = engine_root / "api_v2.py"
    config = engine_root / "GPT_SoVITS" / "configs" / "tts_infer.yaml"
    if not api_script.is_file() or not config.is_file():
        raise TTSServiceError("GPT-SoVITS API files are incomplete.")

    host, port = address
    command = [
        str(python),
        str(api_script),
        "-a",
        host,
        "-p",
        str(port),
        "-c",
        str(config),
    ]
    environment = os.environ.copy()
    runtime_dir = str(python.parent)
    environment["PATH"] = (
        runtime_dir
        + os.pathsep
        + environment.get("PATH", "")
    )
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    return command, environment


def _locate_runtime_python(
    engine_root: Path,
    platform_runtime: PlatformRuntime | None = None,
) -> Path:
    candidates = (
        (platform_runtime or get_platform_runtime())
        .processes.runtime_python_candidates(engine_root)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.absolute()
    raise TTSServiceError(
        "GPT-SoVITS does not contain a bundled Python runtime."
    )


def _report(callback: ProgressCallback | None, stage: str) -> None:
    if callback is not None:
        callback(stage)


_SERVICE_MANAGER: LocalTTSServiceManager | None = None


def get_tts_service_manager(
    platform_runtime: PlatformRuntime | None = None,
) -> LocalTTSServiceManager:
    global _SERVICE_MANAGER
    if _SERVICE_MANAGER is None:
        _SERVICE_MANAGER = LocalTTSServiceManager(platform_runtime)
    return _SERVICE_MANAGER


def shutdown_tts_service() -> None:
    if _SERVICE_MANAGER is not None:
        _SERVICE_MANAGER.shutdown()


atexit.register(shutdown_tts_service)
