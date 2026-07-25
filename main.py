from __future__ import annotations

import sys

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from classes.murasame_class import Murasame
from tool.config import (
    AppSettings,
    PROJECT_ROOT,
    load_settings,
    save_settings,
    settings_file_exists,
)
from ui.settings_dialog import SettingsDialog


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
            "Speech input unavailable",
            f"Install requirements-voice.txt to enable it: {exc}",
            QSystemTrayIcon.Warning,
        )
        return None

    bridge = VoiceBridge(pet)
    bridge.text_ready.connect(lambda text: pet.start_thread(text, role="user"))
    bridge.record_start.connect(
        lambda: pet.show_text("正在录音……", typing=False)
    )
    bridge.record_end.connect(
        lambda: pet.show_text("正在识别……", typing=False)
    )
    bridge.error.connect(
        lambda message: tray_icon.showMessage(
            "Speech input failed",
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
            "Speech input failed",
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
    icon = QIcon(str(PROJECT_ROOT / "icon.png"))
    app.setWindowIcon(icon)

    settings, load_error = load_settings_safely()
    first_run = not settings_file_exists()
    if load_error:
        QMessageBox.warning(
            None,
            "Invalid configuration",
            "The saved configuration could not be read. "
            f"Defaults will be shown instead.\n\n{load_error}",
        )
        first_run = True

    if first_run:
        setup = SettingsDialog(settings, first_run=True)
        if setup.exec_() != QDialog.Accepted:
            return 0
        settings = setup.result_settings()
        save_settings(settings)

    try:
        pet = Murasame(settings)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "AIpet startup failed",
            str(exc),
        )
        return 1
    pet.show()
    move_pet_to_configured_screen(app, pet, settings)

    tray_icon = QSystemTrayIcon(icon, app)
    tray_menu = QMenu()
    settings_action = QAction("Settings Studio…", tray_menu)
    dnd_action = QAction("Do Not Disturb", tray_menu)
    dnd_action.setCheckable(True)
    screenshot_action = QAction("Screen Vision", tray_menu)
    screenshot_action.setCheckable(True)
    screenshot_action.setChecked(pet.is_screenshot_enabled())
    clear_action = QAction("Clear Conversation Memory", tray_menu)
    exit_action = QAction("Exit", tray_menu)

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
                "Settings save failed",
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

    def open_settings() -> None:
        nonlocal settings, voice_trigger
        dialog = SettingsDialog(pet.settings, parent=None)
        if dialog.exec_() != QDialog.Accepted:
            return
        settings = dialog.result_settings()
        try:
            save_settings(settings)
        except OSError as exc:
            QMessageBox.warning(None, "Settings save failed", str(exc))
            return

        if voice_trigger is not None:
            voice_trigger.stop()
        voice_trigger = configure_voice_trigger(pet, settings, tray_icon)
        pet.apply_settings(settings)
        screenshot_action.blockSignals(True)
        screenshot_action.setChecked(settings.vision.enabled)
        screenshot_action.blockSignals(False)
        move_pet_to_configured_screen(app, pet, settings)

    settings_action.triggered.connect(open_settings)

    def shutdown() -> None:
        if voice_trigger is not None:
            voice_trigger.stop()
        persist_pet_settings()
        pet.shutdown()
        tray_icon.hide()

    app.aboutToQuit.connect(shutdown)
    exit_action.triggered.connect(app.quit)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
