from __future__ import annotations

import subprocess
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from tool.config import PROJECT_ROOT
from tool.runtime_logging import get_logger


logger = get_logger("macos-overlay")
HEAD_PAT_COMMAND = "__murasame_head_pat__"


class MacOSFullscreenOverlay:
    """Bridge the Qt pet to a native panel in macOS fullscreen Spaces."""

    def __init__(self, app: QApplication, pet) -> None:
        self.pet = pet
        self.process: subprocess.Popen[bytes] | None = None
        self.fullscreen = False
        self.command_mtime = 0
        self.directory = pet.native_overlay_directory
        self.state_path = self.directory / "fullscreen.state"
        self.visibility_path = self.directory / "qt_visible.state"
        self.command_path = self.directory / "command.txt"
        self.timer = QTimer(app)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.sync)

    def start(self) -> None:
        if sys.platform != "darwin":
            return
        binary = PROJECT_ROOT / ".native_overlay" / "murasame_overlay"
        portrait = self.directory / "portrait.png"
        if not binary.is_file() or not portrait.is_file():
            logger.warning("macOS 全屏兼容组件不可用，继续使用普通桌宠窗口")
            return

        self.directory.mkdir(parents=True, exist_ok=True)
        self.command_path.write_text("", encoding="utf-8")
        self._write_qt_visibility()
        self.process = subprocess.Popen(
            [
                str(binary),
                str(portrait),
                str(self.directory / "text.txt"),
                str(self.state_path),
                str(self.visibility_path),
                str(self.command_path),
            ],
            cwd=str(PROJECT_ROOT),
        )
        self.timer.start()
        logger.info("macOS 原生全屏兼容组件已启动")

    def sync(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self.timer.stop()
            return
        self._write_qt_visibility()
        self._consume_command()
        try:
            fullscreen = (
                self.state_path.read_text(encoding="utf-8").strip() == "1"
            )
        except OSError:
            fullscreen = False
        if fullscreen == self.fullscreen:
            return

        self.fullscreen = fullscreen
        if fullscreen:
            self.pet.hide()
            logger.info("已切换至 macOS 全屏兼容窗口")
        else:
            self.pet.show()
            logger.info("已恢复 Qt 桌宠窗口")
        self._write_qt_visibility()

    def _consume_command(self) -> None:
        try:
            modified = self.command_path.stat().st_mtime_ns
            if modified <= self.command_mtime:
                return
            self.command_mtime = modified
            command = self.command_path.read_text(encoding="utf-8").strip()
            if not command:
                return
            self.command_path.write_text("", encoding="utf-8")
            if command == HEAD_PAT_COMMAND:
                self.pet.start_thread("主人摸了摸你的头。", role="system")
            else:
                self.pet.start_thread(command, role="user")
        except (OSError, UnicodeError):
            pass

    def _write_qt_visibility(self) -> None:
        try:
            self.visibility_path.write_text(
                "1\n" if self.pet.isVisible() else "0\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def stop(self) -> None:
        self.timer.stop()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
