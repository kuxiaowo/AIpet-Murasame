"""Native compatibility panel for other apps' fullscreen Spaces."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from aipet.core.runtime_logging import get_logger


logger = get_logger("macos-overlay")


class FullscreenOverlay:
    def __init__(self, widget: Any) -> None:
        self._widget = widget
        self._process: subprocess.Popen[bytes] | None = None
        self._last_command_mtime = 0
        self._was_fullscreen = False
        self._root = Path(tempfile.gettempdir()) / "aipet-macos-overlay"
        self._image = self._root / "pet.png"
        self._state = self._root / "fullscreen.state"
        self._visibility = self._root / "qt-visible.state"
        self._command = self._root / "command.txt"

    @staticmethod
    def _binary() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parents[1] / "Resources" / "aipet-fullscreen-overlay"
        return Path(__file__).resolve().parents[3] / "build" / "macos" / "aipet-fullscreen-overlay"

    def start(self) -> bool:
        binary = self._binary()
        if not binary.is_file():
            logger.warning("原生全屏兼容组件不存在：%s", binary)
            return False
        self._root.mkdir(parents=True, exist_ok=True)
        self._snapshot()
        self._state.write_text("0\n", encoding="utf-8")
        self._visibility.write_text("1\n", encoding="utf-8")
        self._command.write_text("", encoding="utf-8")
        self._process = subprocess.Popen(
            [str(binary), str(self._image), str(self._state), str(self._visibility), str(self._command)],
            start_new_session=True,
        )
        return True

    @property
    def is_fullscreen(self) -> bool:
        return self._was_fullscreen

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def sync(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        fullscreen = self._state.read_text(encoding="utf-8").strip() == "1"
        if fullscreen and not self._was_fullscreen:
            self._widget.hide()
        elif self._was_fullscreen and not fullscreen:
            self._widget.show()
        self._was_fullscreen = fullscreen
        self._visibility.write_text(
            "1\n" if self._widget.isVisible() else "0\n",
            encoding="utf-8",
        )
        self._snapshot()
        try:
            modified = self._command.stat().st_mtime_ns
        except OSError:
            return
        if modified <= self._last_command_mtime:
            return
        self._last_command_mtime = modified
        text = self._command.read_text(encoding="utf-8").strip()
        self._command.write_text("", encoding="utf-8")
        if text:
            self._widget.start_thread(text, role="user")

    def _snapshot(self) -> None:
        self._widget.grab().save(str(self._image), "PNG")
