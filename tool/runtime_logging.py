from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import TextIO


LOGGER_NAME = "aipet"
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
LEGACY_LOG_PATH = LOG_DIRECTORY / "aipet.log"
LOG_VIEWER = Path(__file__).with_name("log_viewer.py")

_file_handler: DailyFileHandler | None = None
_viewer_process: subprocess.Popen | None = None
_original_excepthook = sys.excepthook

_base_logger = logging.getLogger(LOGGER_NAME)
_base_logger.setLevel(logging.INFO)
_base_logger.propagate = False
_base_logger.addHandler(logging.NullHandler())


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
) -> float:
    logger.info("请求开始 | %s %s", method.upper(), url)
    return time.monotonic()


def log_response(
    logger: logging.Logger,
    method: str,
    url: str,
    status_code: int,
    started_at: float,
) -> None:
    elapsed_ms = (time.monotonic() - started_at) * 1_000
    logger.info(
        "请求完成 | %s %s | HTTP %s | %.0f ms",
        method.upper(),
        url,
        status_code,
        elapsed_ms,
    )


def _ensure_viewer() -> bool:
    global _viewer_process

    if _viewer_process is not None and _viewer_process.poll() is None:
        return True
    if os.name != "nt":
        return False

    try:
        _viewer_process = subprocess.Popen(
            [
                sys.executable,
                str(LOG_VIEWER),
                str(LOG_DIRECTORY),
                str(os.getpid()),
            ],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except OSError:
        _viewer_process = None
        get_logger("startup").exception("无法打开实时日志窗口")
        return False
    return True


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
