import sys
import threading
import json

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QAction, QMenu

from classes.murasame_class import Murasame
from api import app as api_app
import uvicorn

from tool.config import get_config


CONFIG = get_config("./config.json")
screen_index = CONFIG["screen_index"]
VOICE_TRIGGER_ENABLED = CONFIG.get("voice_trigger")


class VoiceBridge(QObject):
    text_ready = pyqtSignal(str)
    record_start = pyqtSignal()
    record_end = pyqtSignal()


def save_screen_type(pet: Murasame) -> None:
    """在程序退出时保存当前截图开关状态到配置文件"""
    try:
        config_path = "./config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["screen_type"] = "true" if pet.is_screenshot_enabled() else "false"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AIpet] 保存 screen_type 失败: {e}")


if __name__ == "__main__":

    # 后台启动本地 API 服务（FastAPI + Uvicorn）
    def _run_api_server():
        config = uvicorn.Config(api_app, host="0.0.0.0", port=28565, log_level="info")
        server = uvicorn.Server(config)
        server.run()

    api_thread = threading.Thread(
        target=_run_api_server,
        name="uvicorn-thread",
        daemon=True,
    )
    api_thread.start()

    app = QApplication(sys.argv)  # 创建应用对象
    pet = Murasame()  # 创建桌宠实例
    app.aboutToQuit.connect(lambda: save_screen_type(pet))
    pet.show()  # 显示窗口

    screens = QApplication.screens()
    target_screen = screens[screen_index]
    geometry = target_screen.availableGeometry()
    pet.move(geometry.x(), geometry.y())

    tray_icon = QSystemTrayIcon(QIcon("icon.png"), parent=app)
    tray_menu = QMenu()

    # 勿扰模式（勾选 = 开启勿扰，不再主动打扰）
    dnd_action = QAction("Do Not Disturb")
    dnd_action.setCheckable(True)
    dnd_action.setChecked(pet.is_dnd_enabled())
    dnd_action.toggled.connect(pet.set_dnd_enabled)

    # 屏幕截图开关（勾选 = 开启截图）
    screenshot_action = QAction("Screenshot")
    screenshot_action.setCheckable(True)
    screenshot_action.setChecked(pet.is_screenshot_enabled())
    screenshot_action.toggled.connect(pet.set_screenshot_enabled)

    clear_action = QAction("Clear History")
    clear_action.triggered.connect(pet.cleer_history)

    # 退出
    exit_action = QAction("Exit")
    exit_action.triggered.connect(app.quit)

    # 菜单绑定
    tray_menu.addAction(dnd_action)
    tray_menu.addAction(screenshot_action)
    tray_menu.addAction(clear_action)
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # ===== CapsLock 语音触发 =====
    if VOICE_TRIGGER_ENABLED == "true":
        from tool.voice_trigger import CapslockVoiceTrigger
        bridge = VoiceBridge()

        bridge.text_ready.connect(lambda text: pet.start_thread(text, role="user"))
        bridge.record_start.connect(
            lambda: pet.show_text("正在录音......", typing=False)
        )
        bridge.record_end.connect(
            lambda: pet.show_text("录音结束，正在识别......", typing=False)
        )

        def _on_voice_text_ready(text: str) -> None:
            bridge.text_ready.emit(text)

        def _on_record_start() -> None:
            bridge.record_start.emit()

        def _on_record_end() -> None:
            bridge.record_end.emit()

        try:
            voice_trigger = CapslockVoiceTrigger(
                on_text_ready=_on_voice_text_ready,
                hold_seconds=2.0,
                on_record_start=_on_record_start,
                on_record_end=_on_record_end,
            )
            voice_trigger.start()
        except Exception as e:
            print(f"[AIpet] 启用 CapsLock 语音触发失败: {e}")
    else:
        print("[AIpet] 已在配置中关闭 CapsLock 语音触发")

    sys.exit(app.exec_())  # 进入事件循环
