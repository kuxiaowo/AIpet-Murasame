from __future__ import annotations

import sys

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
    index = settings.display.screen_index
    screen = (
        screens[index]
        if 0 <= index < len(screens)
        else app.primaryScreen()
    )
    if screen is not None:
        geometry = screen.availableGeometry()
        pet.move(geometry.x(), geometry.y())


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
        lambda: pet.show_text(ui_text(settings, "recording"), typing=False)
    )
    bridge.record_end.connect(
        lambda: pet.show_text(
            ui_text(settings, "recognizing"),
            typing=False,
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
        device=settings.stt.device,
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

    tray_icon = QSystemTrayIcon(icon, app)
    tray_menu = QMenu()
    settings_action = QAction(tray_menu)
    dnd_action = QAction(tray_menu)
    dnd_action.setCheckable(True)
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

    screenshot_action.toggled.connect(set_screen_vision)
    dnd_action.toggled.connect(pet.set_dnd_enabled)
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
