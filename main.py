from __future__ import annotations

import sys
import subprocess

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from classes.download_manager import DownloadManager
from classes.murasame_class import Murasame
from tool.config import (
    AppSettings,
    PROJECT_ROOT,
    load_settings,
    save_settings,
    settings_file_exists,
)
from tool.runtime_logging import (
    configure_console_logging,
    get_logger,
    shutdown_console_logging,
)
from ui.settings_dialog import SettingsDialog
from tool.tts_service import shutdown_tts_service


logger = get_logger("main")


UI_TEXT = {
    "en": {
        "speech_unavailable": "Speech input unavailable",
        "install_voice": "Install requirements-voice.txt to enable it: {error}",
        "speech_failed": "Speech input failed",
        "recording": "Recording…",
        "recognizing": "Recognizing speech…",
        "settings": "Settings…",
        "dnd": "Do Not Disturb",
        "vision": "Screen Vision",
        "clear": "Clear Conversation Memory",
        "exit": "Exit",
        "save_failed": "Settings save failed",
    },
    "zh-CN": {
        "speech_unavailable": "语音输入不可用",
        "install_voice": "请安装 requirements-voice.txt：{error}",
        "speech_failed": "语音输入失败",
        "recording": "正在录音……",
        "recognizing": "正在识别……",
        "settings": "设置…",
        "dnd": "勿扰模式",
        "vision": "屏幕视觉",
        "clear": "清除对话记忆",
        "exit": "退出",
        "save_failed": "设置保存失败",
    },
}


def ui_text(settings: AppSettings, key: str, **values: object) -> str:
    language = (
        settings.ui_language
        if settings.ui_language in UI_TEXT
        else "en"
    )
    text = UI_TEXT[language][key]
    return text.format(**values) if values else text


class VoiceBridge(QObject):
    text_ready = pyqtSignal(str)
    record_start = pyqtSignal()
    record_end = pyqtSignal()
    error = pyqtSignal(str)


class MacNativeOverlay:
    """Keep the standard Qt pet visible in macOS fullscreen Spaces."""

    def __init__(self, app: QApplication, pet: Murasame) -> None:
        self.app = app
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
            fullscreen = self.state_path.read_text(encoding="utf-8").strip() == "1"
        except OSError:
            fullscreen = False
        if fullscreen == self.fullscreen:
            return
        self.fullscreen = fullscreen
        if fullscreen:
            self.pet.hide()
            self._write_qt_visibility()
            logger.info("已切换至 macOS 全屏兼容窗口")
        else:
            self.pet.show()
            self._write_qt_visibility()
            logger.info("已恢复 Qt 桌宠窗口")

    def _consume_command(self) -> None:
        try:
            modified = self.command_path.stat().st_mtime_ns
            if modified <= self.command_mtime:
                return
            self.command_mtime = modified
            text = self.command_path.read_text(encoding="utf-8").strip()
            if text:
                self.command_path.write_text("", encoding="utf-8")
                self.pet.start_thread(text, role="user")
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


def load_settings_safely() -> tuple[AppSettings, str | None]:
    try:
        return load_settings(), None
    except Exception as exc:
        return AppSettings(), str(exc)


def move_pet_to_configured_screen(
    app: QApplication,
    pet: Murasame,
    settings: AppSettings,
) -> None:
    screens = app.screens()
    display = settings.display
    screen = next(
        (
            candidate
            for candidate in screens
            if display.screen_name
            and candidate.name() == display.screen_name
        ),
        None,
    )
    index = display.screen_index
    screen = (
        screen
        or (
            screens[index]
            if 0 <= index < len(screens)
            else app.primaryScreen()
        )
    )
    if screen is not None:
        geometry = screen.availableGeometry()
        x = geometry.x()
        y = geometry.y()
        if display.window_x is not None and display.window_y is not None:
            x += display.window_x
            y += display.window_y
            max_x = max(geometry.left(), geometry.right() - pet.width() + 1)
            max_y = max(geometry.top(), geometry.bottom() - pet.height() + 1)
            x = max(geometry.left(), min(x, max_x))
            y = max(geometry.top(), min(y, max_y))
        pet.move(x, y)
        pet.remember_window_position()


def configure_voice_trigger(
    pet: Murasame,
    settings: AppSettings,
    tray_icon: QSystemTrayIcon,
):
    if not settings.stt.enabled:
        return None

    try:
        from tool.voice_trigger import CapslockVoiceTrigger
    except ImportError as exc:
        tray_icon.showMessage(
            ui_text(settings, "speech_unavailable"),
            ui_text(settings, "install_voice", error=exc),
            QSystemTrayIcon.Warning,
        )
        return None

    bridge = VoiceBridge(pet)
    bridge.text_ready.connect(lambda text: pet.start_thread(text, role="user"))
    bridge.record_start.connect(
        lambda: pet.show_text(
            ui_text(settings, "recording"),
            typing=False,
            speaker_name=settings.character.user_name,
        )
    )
    bridge.record_end.connect(
        lambda: pet.show_text(
            ui_text(settings, "recognizing"),
            typing=False,
            speaker_name=settings.character.user_name,
        )
    )
    bridge.error.connect(
        lambda message: tray_icon.showMessage(
            ui_text(settings, "speech_failed"),
            message,
            QSystemTrayIcon.Warning,
        )
    )

    trigger = CapslockVoiceTrigger(
        on_text_ready=bridge.text_ready.emit,
        hold_seconds=2.0,
        on_record_start=bridge.record_start.emit,
        on_record_end=bridge.record_end.emit,
        model_name=settings.stt.model,
        model_directory=settings.stt.model_dir,
        device=settings.stt.device,
        input_device=settings.stt.input_device,
        on_error=bridge.error.emit,
    )
    try:
        trigger.start()
    except Exception as exc:
        tray_icon.showMessage(
            ui_text(settings, "speech_failed"),
            str(exc),
            QSystemTrayIcon.Warning,
        )
        return None
    trigger._qt_bridge = bridge
    return trigger


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AIpet Murasame")
    app.setFont(QFont("Segoe UI", 10))
    app.setQuitOnLastWindowClosed(False)
    download_manager = DownloadManager(app)
    icon = QIcon(str(PROJECT_ROOT / "icon.png"))
    app.setWindowIcon(icon)

    settings, load_error = load_settings_safely()
    configure_console_logging(settings.display.show_log_console)
    logger.info(
        "配置已加载 | 对话后端=%s | 视觉后端=%s",
        settings.mode,
        settings.vision.provider,
    )
    first_run = not settings_file_exists()
    if load_error:
        logger.error("读取配置失败：%s", load_error)
        QMessageBox.warning(
            None,
            "Invalid configuration",
            "The saved configuration could not be read. "
            f"Defaults will be shown instead.\n\n{load_error}",
        )
        first_run = True

    if first_run:
        setup = SettingsDialog(
            settings,
            first_run=True,
            download_manager=download_manager,
        )
        if setup.exec_() != QDialog.Accepted:
            download_manager.shutdown()
            return 0
        settings = setup.result_settings()
        save_settings(settings)
        configure_console_logging(settings.display.show_log_console)

    try:
        pet = Murasame(settings)
    except Exception as exc:
        logger.exception("AIpet 启动失败")
        QMessageBox.critical(
            None,
            "AIpet startup failed",
            str(exc),
        )
        download_manager.shutdown()
        return 1
    pet.show()
    move_pet_to_configured_screen(app, pet, settings)
    native_overlay = MacNativeOverlay(app, pet)
    native_overlay.start()

    tray_icon = QSystemTrayIcon(icon, app)
    tray_menu = QMenu()
    settings_action = QAction(tray_menu)
    dnd_action = QAction(tray_menu)
    dnd_action.setCheckable(True)
    dnd_action.setChecked(pet.is_dnd_enabled())
    screenshot_action = QAction(tray_menu)
    screenshot_action.setCheckable(True)
    screenshot_action.setChecked(pet.is_screenshot_enabled())
    clear_action = QAction(tray_menu)
    exit_action = QAction(tray_menu)

    def apply_tray_language(current_settings: AppSettings) -> None:
        settings_action.setText(ui_text(current_settings, "settings"))
        dnd_action.setText(ui_text(current_settings, "dnd"))
        screenshot_action.setText(ui_text(current_settings, "vision"))
        clear_action.setText(ui_text(current_settings, "clear"))
        exit_action.setText(ui_text(current_settings, "exit"))

    apply_tray_language(settings)

    tray_menu.addAction(settings_action)
    tray_menu.addSeparator()
    tray_menu.addAction(dnd_action)
    tray_menu.addAction(screenshot_action)
    tray_menu.addAction(clear_action)
    tray_menu.addSeparator()
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    pet.notification.connect(
        lambda title, message: tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.Warning,
        )
    )

    voice_trigger = configure_voice_trigger(pet, settings, tray_icon)

    def persist_pet_settings() -> None:
        pet.remember_window_position()
        try:
            save_settings(pet.settings)
        except OSError as exc:
            tray_icon.showMessage(
                ui_text(pet.settings, "save_failed"),
                str(exc),
                QSystemTrayIcon.Warning,
            )

    def set_screen_vision(enabled: bool) -> None:
        pet.set_screenshot_enabled(enabled)
        screenshot_action.blockSignals(True)
        screenshot_action.setChecked(pet.is_screenshot_enabled())
        screenshot_action.blockSignals(False)
        persist_pet_settings()

    def set_do_not_disturb(enabled: bool) -> None:
        pet.set_dnd_enabled(enabled)
        dnd_action.blockSignals(True)
        dnd_action.setChecked(pet.is_dnd_enabled())
        dnd_action.blockSignals(False)
        persist_pet_settings()

    screenshot_action.toggled.connect(set_screen_vision)
    dnd_action.toggled.connect(set_do_not_disturb)
    clear_action.triggered.connect(pet.clear_history)

    settings_dialog: SettingsDialog | None = None

    def apply_settings_dialog(dialog: SettingsDialog) -> None:
        nonlocal settings, voice_trigger
        settings = dialog.result_settings()
        try:
            save_settings(settings)
        except OSError as exc:
            QMessageBox.warning(
                None,
                ui_text(settings, "save_failed"),
                str(exc),
            )
            return

        configure_console_logging(settings.display.show_log_console)
        logger.info(
            "设置已应用 | 对话后端=%s | 视觉后端=%s",
            settings.mode,
            settings.vision.provider,
        )
        if voice_trigger is not None:
            voice_trigger.stop()
        voice_trigger = configure_voice_trigger(pet, settings, tray_icon)
        pet.apply_settings(settings)
        apply_tray_language(settings)
        dnd_action.blockSignals(True)
        dnd_action.setChecked(pet.is_dnd_enabled())
        dnd_action.blockSignals(False)
        screenshot_action.blockSignals(True)
        screenshot_action.setChecked(settings.vision.enabled)
        screenshot_action.blockSignals(False)
        move_pet_to_configured_screen(app, pet, settings)

    def finish_settings_dialog(
        result: int,
        dialog: SettingsDialog,
    ) -> None:
        nonlocal settings_dialog
        if result == QDialog.Accepted:
            apply_settings_dialog(dialog)
        if settings_dialog is dialog:
            settings_dialog = None
        dispose_settings_dialog_when_idle(dialog)

    def dispose_settings_dialog_when_idle(
        dialog: SettingsDialog,
    ) -> None:
        if dialog._background_check_is_running():
            QTimer.singleShot(
                100,
                lambda current=dialog: (
                    dispose_settings_dialog_when_idle(current)
                ),
            )
            return
        dialog.deleteLater()

    def open_settings() -> None:
        nonlocal settings_dialog
        if settings_dialog is not None:
            settings_dialog.showNormal()
            settings_dialog.raise_()
            settings_dialog.activateWindow()
            return

        dialog = SettingsDialog(
            pet.settings,
            download_manager=download_manager,
            parent=None,
        )
        dialog.clear_history_requested.connect(pet.clear_history)
        settings_dialog = dialog
        dialog.finished.connect(
            lambda result, current=dialog: finish_settings_dialog(
                result,
                current,
            )
        )
        dialog.open()

    settings_action.triggered.connect(open_settings)

    def shutdown() -> None:
        logger.info("AIpet 正在退出")
        native_overlay.stop()
        if voice_trigger is not None:
            voice_trigger.stop()
        persist_pet_settings()
        pet.shutdown()
        shutdown_tts_service()
        download_manager.shutdown()
        tray_icon.hide()
        shutdown_console_logging()

    app.aboutToQuit.connect(shutdown)
    exit_action.triggered.connect(app.quit)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
