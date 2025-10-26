import sys
import threading

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QAction, QMenu

from classes import Murasame  # 从 classes 包引入你的桌宠类
from api import app as api_app  # 引入 FastAPI 应用以便在本进程中启动
import uvicorn

if __name__ == "__main__":

    # 后台启动本地 API 服务（FastAPI + Uvicorn）
    def _run_api_server():
        # 使用对象方式配置，避免事件循环冲突
        config = uvicorn.Config(api_app, host="0.0.0.0", port=28565, log_level="info")
        server = uvicorn.Server(config)
        server.run()

    api_thread = threading.Thread(target=_run_api_server, name="uvicorn-thread", daemon=True)
    api_thread.start()

    app = QApplication(sys.argv) ## 创建应用对象
    pet = Murasame()#创建桌宠实例
    pet.show()#显示窗口
    tray_icon = QSystemTrayIcon(QIcon("icon.png"), parent=app)
    tray_menu = QMenu()

    clear_action = QAction("Clear History")
    clear_action.triggered.connect(pet.cleer_history)

    # 退出
    exit_action = QAction("Exit")
    exit_action.triggered.connect(app.quit)

    # 菜单绑定
    tray_menu.addAction(clear_action)
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    sys.exit(app.exec_())#进入事件循环
