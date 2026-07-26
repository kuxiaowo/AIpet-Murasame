from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO

from tool.config import get_user_data_dir


LOGGER_NAME = "aipet"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = get_user_data_dir() / "logs"
LEGACY_LOG_PATH = PROJECT_ROOT / "logs" / "aipet.log"
LOG_VIEWER = Path(__file__).with_name("log_viewer.py")

_file_handler: DailyFileHandler | None = None
_viewer_process: subprocess.Popen | None = None
_original_excepthook = sys.excepthook

_base_logger = logging.getLogger(LOGGER_NAME)
_base_logger.setLevel(logging.INFO)
_base_logger.propagate = False
_base_logger.addHandler(logging.NullHandler())


@dataclass(frozen=True)
class RequestLogContext:
    request_id: str
    started_at: float


class DailyFileHandler(logging.Handler):
    """Write UTF-8 logs to one file per local calendar day."""

    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self._day = ""
        self._stream: TextIO | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ensure_stream()
            assert self._stream is not None
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        super().close()

    def _ensure_stream(self) -> None:
        current_day = date.today().isoformat()
        if self._stream is not None and self._day == current_day:
            return
        if self._stream is not None:
            self._stream.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._stream = (self.directory / f"{current_day}.log").open(
            "a",
            encoding="utf-8",
            buffering=1,
        )
        self._day = current_day


def get_logger(component: str | None = None) -> logging.Logger:
    name = LOGGER_NAME if not component else f"{LOGGER_NAME}.{component}"
    return logging.getLogger(name)


def configure_console_logging(enabled: bool) -> bool:
    """Enable or disable AIpet's independent live diagnostic window."""
    global _file_handler

    if not enabled:
        _stop_viewer()
        if _file_handler is not None:
            _base_logger.removeHandler(_file_handler)
            _file_handler.close()
            _file_handler = None
        sys.excepthook = _original_excepthook
        return False

    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_log()

    if _file_handler is None:
        handler = DailyFileHandler(LOG_DIRECTORY)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        _base_logger.addHandler(handler)
        _file_handler = handler
        sys.excepthook = _log_unhandled_exception

    viewer_started = _ensure_viewer()
    get_logger("startup").info(
        "实时日志已启用 | Python %s | PID %s | 日志=%s",
        sys.version.split()[0],
        os.getpid(),
        LOG_DIRECTORY / f"{date.today().isoformat()}.log",
    )
    return viewer_started


def shutdown_console_logging() -> None:
    get_logger("startup").info("实时日志查看器即将关闭")
    configure_console_logging(False)


def log_request(
    logger: logging.Logger,
    method: str,
    url: str,
    payload: Any = None,
) -> RequestLogContext:
    context = RequestLogContext(
        request_id=uuid.uuid4().hex[:8],
        started_at=time.monotonic(),
    )
    logger.info(
        "请求发出 | ID=%s | %s %s | JSON=\n%s",
        context.request_id,
        method.upper(),
        url,
        format_json_for_log({} if payload is None else payload),
    )
    return context


def log_response(
    logger: logging.Logger,
    method: str,
    url: str,
    status_code: int,
    context: RequestLogContext,
    payload: Any,
) -> None:
    elapsed_ms = (time.monotonic() - context.started_at) * 1_000
    logger.info(
        "收到响应 | ID=%s | %s %s | HTTP %s | %.0f ms | JSON=\n%s",
        context.request_id,
        method.upper(),
        url,
        status_code,
        elapsed_ms,
        format_json_for_log(payload),
    )


def log_event(
    logger: logging.Logger,
    event: str,
    **details: Any,
) -> None:
    logger.info(
        "事件 | %s | JSON=%s",
        event,
        format_json_for_log(details, indent=None),
    )


def format_json_for_log(payload: Any, *, indent: int | None = 2) -> str:
    """Serialize JSON safely while keeping diagnostic data readable.

    Image/audio base64 blobs are represented by metadata. Logging those blobs
    verbatim would rapidly create multi-gigabyte daily logs and make the live
    viewer unusable.
    """
    sanitized = _sanitize_log_value(payload)
    try:
        return json.dumps(
            sanitized,
            ensure_ascii=False,
            indent=indent,
            default=str,
        )
    except (TypeError, ValueError):
        return json.dumps(
            {"unserializable": repr(sanitized)},
            ensure_ascii=False,
            indent=indent,
        )


def _sanitize_log_value(value: Any, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if normalized_key in {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }:
        return "<已脱敏>"
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize_log_value(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_log_value(item, key) for item in value]
    if isinstance(value, str) and _looks_like_base64_blob(
        value,
        normalized_key,
    ):
        digest = hashlib.sha256(
            value.encode("ascii", errors="ignore")
        ).hexdigest()
        media_type = "base64"
        if value.startswith("data:"):
            media_type = value[5:].split(";", 1)[0] or media_type
        return (
            f"<{media_type} 数据已省略；字符数={len(value)}；"
            f"sha256={digest}>"
        )
    return value


def _looks_like_base64_blob(value: str, key: str) -> bool:
    if value.startswith("data:") and ";base64," in value[:128]:
        return True
    return key in {"image", "images", "audio"} and len(value) > 1_024


def _ensure_viewer() -> bool:
    global _viewer_process

    if _viewer_process is not None and _viewer_process.poll() is None:
        return True
    if os.name != "nt":
        return False

    try:
        _viewer_process = subprocess.Popen(
            _viewer_command(LOG_DIRECTORY, os.getpid()),
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
    except OSError:
        _viewer_process = None
        get_logger("startup").exception("无法打开实时日志窗口")
        return False
    return True


def _viewer_command(
    log_directory: Path,
    parent_process_id: int,
) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--log-viewer",
            str(log_directory),
            str(parent_process_id),
        ]

    return [
        _console_python_executable(sys.executable),
        str(LOG_VIEWER),
        str(log_directory),
        str(parent_process_id),
    ]


def _console_python_executable(executable: str) -> str:
    """Use python.exe even when the Qt application was started by pythonw.exe."""
    path = Path(executable)
    if path.name.lower() != "pythonw.exe":
        return str(path)
    console_python = path.with_name("python.exe")
    return str(console_python) if console_python.is_file() else str(path)


def _migrate_legacy_log() -> None:
    if not LEGACY_LOG_PATH.is_file():
        return
    try:
        legacy_day = datetime.fromtimestamp(
            LEGACY_LOG_PATH.stat().st_mtime
        ).date().isoformat()
        destination = LOG_DIRECTORY / f"{legacy_day}.log"
        if not destination.exists():
            LEGACY_LOG_PATH.replace(destination)
            return
        with destination.open("ab") as output:
            output.write(LEGACY_LOG_PATH.read_bytes())
        LEGACY_LOG_PATH.unlink()
    except OSError:
        # A previous AIpet process may still have the legacy file open.
        return


def _stop_viewer() -> None:
    global _viewer_process

    process = _viewer_process
    _viewer_process = None
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def _log_unhandled_exception(
    exc_type,
    exc_value,
    traceback,
) -> None:
    get_logger("crash").critical(
        "未处理异常",
        exc_info=(exc_type, exc_value, traceback),
    )
    _original_excepthook(exc_type, exc_value, traceback)
