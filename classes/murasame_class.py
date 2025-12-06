import json
import os
import time
import textwrap
import wave
import ctypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QGuiApplication, QImage
from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QFontMetrics
from PyQt5.QtMultimedia import QSound
from PyQt5.QtWidgets import QLabel

from classes.Worker_class import ScreenWorker
from classes.Worker_class import qwen3_lora_Worker, cloud_API_Worker
from tool.config import get_config
from tool.chat import ollama_qwen25vl
from tool.cloud_API_chat import cloud_vl
from tool.generate import generate_fgimage


def wrap_text(s, width=10):
    return "\n".join(
        textwrap.wrap(
            s,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )


CONFIG = get_config("./config.json")
portrait_type = CONFIG["portrait"]
model_type = CONFIG["model_type"]
screen_type = CONFIG.get("screen_type", "true")
DEFAULT_PORTRAIT_SCREEN_RATIO = CONFIG["DEFAULT_PORTRAIT_SCREEN_RATIO"]
IDLE_THINKING_MINUTES = CONFIG.get("idle_thinking_minutes")
IDLE_AWAY_MINUTES = CONFIG.get("idle_away_minutes")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_seconds() -> float:
    """基于 Windows GetLastInputInfo 计算全局空闲时间（秒）"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except AttributeError:
        # 非 Windows 平台直接认为无空闲
        return 0.0

    last_input_info = LASTINPUTINFO()
    last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(last_input_info)):
        return 0.0

    tick_count = kernel32.GetTickCount()
    idle_ms = tick_count - last_input_info.dwTime
    if idle_ms < 0:
        idle_ms = 0
    return idle_ms / 1000.0


class Murasame(QLabel):
    # 初始
    def __init__(self):
        super().__init__()
        # 文字
        self.full_text = ""  # 打字机效果用到的整体字符串
        self.pet_name = "丛雨"  # 宠物名称
        self.user_name = CONFIG["user_name"]  # 用户名字
        self.display_text = ""  # 将要展示的文字
        self._font_family = "思源黑体Bold.otf"
        self._base_font_size = 40
        self._base_text_x_offset = 140  # 文本框左右偏移量
        self._base_text_y_offset = -100  # 文本框上下偏移量
        self._base_border_size = 2
        self._current_scale = 1.0
        self.border_size = self._base_border_size
        self._update_text_scaling()

        # 创建打字机效果的计时器
        self.typing_timer = QTimer(self)
        self.typing_speed = 40
        self.typing_timer.setInterval(self.typing_speed)  # 每 40 毫秒触发一次（打字机速度）

        # 输入
        self.input_mode = False  # 是否处于输入模式
        self.input_buffer = ""  # 输入模式下已确认的文字
        self.preedit_text = ""  # 输入模式下的拼音/候选
        self.setFocusPolicy(Qt.StrongFocus)  # 接收键盘焦点
        self.setAttribute(Qt.WA_InputMethodEnabled, True)  # 开启输入法支持
        self.setFocus()
        # 鼠标事件
        self.touch_head = False  # 是否正在摸头（左键点头部后进入判定）
        self.head_press_x = None  # 按下头部时的横坐标，用来判断是否“晃动”
        self.offset = None  # 中键拖动时记录的偏移量

        # AI 对话
        self.history = []
        self.portrait_history = []
        self.screen_history = ["", ""]
        self.history_file = Path("./data/history.json")
        self._load_history()

        # 初始立绘
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )  # 去掉标题栏和边框，窗口总在最前面，任务栏不单独显示图标
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 让整个窗口支持透明区域
        if portrait_type == "a":
            self.first_portrait = [1950, 1368, 1958]
        elif portrait_type == "b":
            self.first_portrait = [1715, 1306, 1719]
        else:
            self.first_portrait = [1715, 1306, 1719]
        self.update_portrait(f"ムラサメ{portrait_type}", self.first_portrait)
        if not self.portrait_history:
            self.portrait_history.append(("", str(self.first_portrait)))
            self._save_history()

        # 线程
        self.worker = None
        self.interval = CONFIG["screen_interval"]
        self._screenshot_worker = None
        self._screenshot_executor = ThreadPoolExecutor(
            max_workers=1
        )  # 处理屏幕截图网络调用
        self.force_stop = False  # 是否处于强制中断状态
        if screen_type == "true":
            QTimer.singleShot(
                1000, lambda: self.start_screenshot_worker(interval=self.interval)
            )

        # 空闲检测相关
        self.idle_thinking_triggered = False
        self.idle_away_triggered = False
        self.idle_thinking_seconds = max(0, IDLE_THINKING_MINUTES) * 60
        self.idle_away_seconds = max(
            self.idle_thinking_seconds + 60,
            max(0, IDLE_AWAY_MINUTES) * 60,
        )

        # 记录离开屏幕的时间，用于回来后问候
        self.away_trigger_time = None

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(1000)
        self.idle_timer.timeout.connect(self.check_idle_state)
        self.idle_timer.start()

        # 勿扰模式：开启后关闭截图与空闲检测，并禁止主动搭话
        self._dnd_enabled = False

    def focusInEvent(self, event):
        """当桌宠获得焦点时（用户点中、开始输入）"""
        # 输入时暂停自动行为，但勿扰模式下保持静默
        if not self.is_dnd_enabled():
            self.pause_all_ai()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """当桌宠失去焦点时（用户点击别处、输入结束）"""
        # 仅在未开启勿扰模式时恢复自动行为
        if not self.is_dnd_enabled():
            self.resume_all_ai()
        super().focusOutEvent(event)

    def start_screenshot_worker(self, interval):
        # 勿扰模式下不启动截图线程
        if getattr(self, "_dnd_enabled", False):
            return
        if self._screenshot_worker and self._screenshot_worker.isRunning():
            return
        self._screenshot_worker = ScreenWorker(interval)
        self._screenshot_worker.screenshot_captured.connect(self.on_screenshot_captured)
        self._screenshot_worker.start()

    def stop_screenshot_worker(self):
        if self._screenshot_worker and self._screenshot_worker.isRunning():
            self._screenshot_worker.requestInterruption()
            self._screenshot_worker.quit()
            self._screenshot_worker.wait()
            self._screenshot_worker = None

    def set_screenshot_enabled(self, enabled: bool):
        global screen_type
        screen_type = "true" if enabled else "false"
        # 持久化当前开关状态，保证即使直接关闭命令行也能保留设置
        try:
            config = get_config("./config.json")
            config["screen_type"] = screen_type
            with open("./config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AIpet] 保存 screen_type 失败: {e}")

        if enabled:
            # 勿扰模式下只记录开关状态，不真正启动截图线程
            if self.is_dnd_enabled():
                print("[AIpet] 勿扰模式开启中：暂不启动截图线程")
                return
            if not (self._screenshot_worker and self._screenshot_worker.isRunning()):
                print("[AIpet] 启用截图线程")
                self.start_screenshot_worker(interval=self.interval)
        else:
            print("[AIpet] 停用截图线程")
            self.stop_screenshot_worker()

    def is_screenshot_enabled(self) -> bool:
        return screen_type == "true"

    def set_dnd_enabled(self, enabled: bool):
        """设置勿扰模式。

        勿扰模式开启后：
        - 停止截图线程
        - 停止空闲检测计时器
        - 不再触发基于空闲或截图的主动对话
        """
        self._dnd_enabled = bool(enabled)
        if self._dnd_enabled:
            print("[AIpet] 启用勿扰模式")
            # 停止一切自动行为
            self.pause_all_ai()
            if self.idle_timer.isActive():
                self.idle_timer.stop()
            # 重置空闲状态，避免退出勿扰后立刻触发
            self.idle_thinking_triggered = False
            self.idle_away_triggered = False
            self.away_trigger_time = None
        else:
            print("[AIpet] 关闭勿扰模式")
            # 恢复空闲检测
            if not self.idle_timer.isActive():
                self.idle_timer.start()
            # 仅当截图功能处于开启状态时恢复截图线程
            if self.is_screenshot_enabled():
                self.resume_all_ai()

    def is_dnd_enabled(self) -> bool:
        return getattr(self, "_dnd_enabled", False)

    def on_screenshot_captured(self, image_path):
        # 勿扰模式下完全忽略截图结果
        if self.is_dnd_enabled():
            try:
                os.remove(image_path)
            except Exception:
                pass
            return
        model_type = get_config("./config.json")["model_type"]

        def task(path):
            try:
                try:
                    if model_type == "deepseek" or model_type == "qwen":
                        if self.force_stop:
                            print("[cloud-vl] 已中断生成")
                            return
                        desc = cloud_vl(path)
                    elif model_type == "local":
                        if self.force_stop:
                            print("[ollama-qwen2.5vl] 已中断生成")
                            return
                        desc = ollama_qwen25vl(path)
                    propmt = (
                        "系统提示：下面是一段对用户当前屏幕内容和正在做的事的描述。"
                        "屏幕描述"
                        f"{desc}"
                    )
                    if self.force_stop:
                        print("屏幕回复 已中断生成")
                        return
                    self.start_thread(propmt, role="system", t=True)
                except Exception as e:
                    print(f"[AIpet] 截图分析失败: {e}")
            finally:
                try:
                    os.remove(path)
                except Exception:
                    pass

        self._screenshot_executor.submit(task, image_path)

    def pause_all_ai(self):
        """用户输入时：停止截图线程、中断 AI 显示与语音"""
        self.force_stop = True  # 启用软中断标记

        if self._screenshot_worker and self._screenshot_worker.isRunning():
            print("[AIpet] 暂停截图线程")
            self.stop_screenshot_worker()
        if self.worker and self.worker.isRunning():
            self.worker.stop_screen()
        try:
            QSound.stop()
        except Exception:
            pass

    def resume_all_ai(self):
        """用户输入结束后：恢复截图线程与 AI 响应"""
        self.force_stop = False  # 解除软中断标记
        if not (self._screenshot_worker and self._screenshot_worker.isRunning()) and (
            screen_type == "true"
        ):
            print("[AIpet] 恢复截图线程")
            self.start_screenshot_worker(interval=self.interval)

    def check_idle_state(self):
        """检查系统空闲时间并在阈值上触发对话"""
        idle_seconds = get_idle_seconds()

        # 如果已经从离开状态回来，并且离开超过 60 秒，则问候一次“欢迎回来”
        if (
                idle_seconds <= self.idle_thinking_seconds
                and self.idle_away_triggered
                and self.away_trigger_time is not None
        ):
            elapsed = time.time() - self.away_trigger_time
            if elapsed >= 30:
                print("[AIpet] 触发回归")
                greeting_prompt = (
                    "系统提示：用户刚刚从离开状态回到电脑前。"
                    "你以“丛雨”的身份，简单打个招呼"
                    "可以说“欢迎回来”、问问主人要不要继续刚才的事情之类，"
                    "回答简短。不要与之前重复。"
                )
                self.start_thread(greeting_prompt, role="system", t=True)
                # 防止重复问候
                self.away_trigger_time = None

        # 有操作时重置状态
        if idle_seconds <= self.idle_thinking_seconds:
            if self.idle_thinking_triggered or self.idle_away_triggered:
                print("[AIpet] 检测到用户活动，重置空闲状态")
            self.idle_thinking_triggered = False
            self.idle_away_triggered = False
            return

        # 超过离屏阈值
        if idle_seconds >= self.idle_away_seconds and not self.idle_away_triggered:
            self.idle_away_triggered = True
            self.away_trigger_time = time.time()
            print(f"[AIpet] 空闲超过 {self.idle_away_seconds} 秒，判定为离开屏幕")
            prompt = (
                "系统提示：用户已经离开屏幕更长时间，没有对电脑进行任何输入。忽视最近的对话。"
                "你需要以“丛雨”的身份，问问主人还在不在，提醒适当休息。"
                "不要和之前问主人走神或是思考的提示重复。"
            )
            # 使用 system 角色注入上下文，对话可以被用户输入打断
            self.start_thread(prompt, role="system", t=True)
            return

        # 超过发呆阈值
        if idle_seconds >= self.idle_thinking_seconds and not self.idle_thinking_triggered:
            self.idle_thinking_triggered = True
            print(f"[AIpet] 空闲超过 {self.idle_thinking_seconds} 秒")
            prompt = (
                "系统提示：用户已经有一段时间没有对电脑进行输入操作。忽视最近的对话。"
                "可能是在发呆、走神或者安静地思考。请你以“丛雨”的身份，"
                "用温柔、贴心但不过分打扰的方式主动搭话，可以简单关心一下主人在想什么，或者是不是走神，在摸鱼，"
                "或者轻轻提醒他注意放松，回答不超过三句话。"
            )
            self.start_thread(prompt, role="system", t=True)

    # qwen3 线程的槽函数
    def on_reply(self, reply, portrait_list, history, portrait_history, voices):
        self.portrait_history = portrait_history
        self.history = history
        self._save_history()

        def show_next_sentence(index=0):
            def get_audio_length_wave(audio_file_path):
                try:
                    with wave.open(audio_file_path, "rb") as wave_file:
                        frames = wave_file.getnframes()  # 获取音频的帧数
                        rate = wave_file.getframerate()  # 获取音频的帧速率
                        duration = frames / float(rate)  # 计算时长（秒）
                        return duration * 1000  # 转换为毫秒
                except Exception:
                    return 0

            if index >= len(reply):
                return
            sentence = reply[index]
            portrait = portrait_list[index]
            self.update_portrait(f"ムラサメ{portrait_type}", portrait)
            voice_id = voices[index]
            voice_path = f"./voices/{voice_id}.wav" if voice_id else None
            voice_length = 0
            if voice_path and os.path.exists(voice_path):
                voice_length = get_audio_length_wave(os.path.abspath(voice_path))
                if voice_length > 0:
                    QSound.play(voice_path)
            self.show_text(sentence, typing=True)
            # 计算打字机需要的时间（40ms * 每个字）
            delay = max(40 * len(sentence) + 800, voice_length + 400)  # 额外停顿
            if voice_path and os.path.exists(voice_path) and voice_length > 0:
                QTimer.singleShot(
                    int(delay),
                    lambda: [os.remove(voice_path), show_next_sentence(index + 1)],
                )
            else:
                QTimer.singleShot(int(delay), lambda: show_next_sentence(index + 1))

        show_next_sentence(index=0)
        self.worker = None  # 线程结束后清空引用

    # 启动一个新线程（安全版，打断旧线程）
    def start_thread(self, text, role, t=False):
        # 结束旧线程
        if self.worker and self.worker.isRunning():
            self.worker.stop_all()  # 通知线程中断
            self.worker.wait(1000)

        # 启动新线程
        if model_type == "local":
            self.worker = qwen3_lora_Worker(
                self.history, self.portrait_history, text, role, t=t
            )
        else:
            self.worker = cloud_API_Worker(
                self.history, self.portrait_history, text, role, t=t
            )

        self.worker.finished.connect(self.on_reply)
        self.worker.start()

    # 鼠标按下事件
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 判断点在哪里
            if event.y() < 150:  # 头部区域
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:  # 下半身区域 -> 输入模式
                self.input_mode = True
                self.input_buffer = ""
                self.preedit_text = ""
                self.display_text = f"【{self.user_name}】\n  ..."
                self.update()
            else:
                # 其他地方，什么也不做
                self.touch_head = False
                self.head_press_x = None
                self.setCursor(Qt.ArrowCursor)

        elif event.button() == Qt.MiddleButton:
            # 中键拖动
            self.offset = event.pos()
            self.setCursor(Qt.SizeAllCursor)

    # 鼠标移动事件
    def mouseMoveEvent(self, event):
        # 判断是不是在“摸头”
        if self.touch_head and self.head_press_x is not None:
            if abs(event.x() - self.head_press_x) > 50:
                self.start_thread("主人摸了摸你的头", role="system")
                self.touch_head = False

        # 中键拖动窗口
        if self.offset is not None and event.buttons() == Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.offset)

    # 鼠标释放事件
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)  # 恢复箭头

        elif event.button() == Qt.MiddleButton:
            self.offset = None
            self.setCursor(Qt.ArrowCursor)  # 拖动结束也要恢复箭头

    # 绘制事件
    def paintEvent(self, event):
        # 1. 先调用 QLabel 默认的绘制（画立绘 / 背景）
        super().paintEvent(event)

        # 2. 再叠加绘制文字
        if self.display_text:  # 过滤掉空字符串和 None
            # 设置绘图环境
            painter = QPainter(self)  # 在这个控件上绘制
            painter.setRenderHint(QPainter.Antialiasing, True)  # 抗锯齿
            painter.setRenderHint(QPainter.TextAntialiasing, True)  # 文字抗锯齿
            painter.setFont(self.text_font)

            rect = self.rect()
            # 调整文字区域（放在立绘上半部分）
            text_rect = rect.adjusted(
                self.text_x_offset,  # 左
                self.text_y_offset,  # 上
                -self.text_x_offset,  # 右
                -rect.height() // 2 + self.text_y_offset,  # 下
            )

            # 如果有换行就靠左对齐，否则居中
            if "\n" in self.display_text:
                align_flag = Qt.AlignLeft | Qt.AlignBottom
            else:
                align_flag = Qt.AlignHCenter | Qt.AlignBottom

            # 文字描边（黑色）
            border_size = self.border_size
            painter.setPen(QColor(44, 22, 28))
            for dx, dy in [
                (-border_size, 0),
                (border_size, 0),
                (0, -border_size),
                (0, border_size),
                (border_size, -border_size),
                (border_size, border_size),
                (-border_size, -border_size),
                (-border_size, border_size),
            ]:
                painter.drawText(text_rect.translated(dx, dy), align_flag, self.display_text)

            # 文字正体（白色）
            painter.setPen(Qt.white)
            painter.drawText(text_rect, align_flag, self.display_text)

            painter.end()

    # 更新立绘
    def update_portrait(self, target, layers):

        # 1. Generate the RGBA numpy image
        cv_img = generate_fgimage(target, layers)

        # 2. Convert RGBA to BGRA to keep colors correct in Qt
        if cv_img.shape[2] == 4:
            cv_img_bgra = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGRA)
        else:
            cv_img_bgra = cv_img

        # 3. Build a QImage from the numpy buffer
        h, w, ch = cv_img_bgra.shape
        bytes_per_line = ch * w
        qimg = QImage(
            cv_img_bgra.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGBA8888,
        )

        # 4. Convert to QPixmap and apply adaptive scaling
        pixmap = QPixmap.fromImage(qimg)
        pixmap = self._scale_portrait_pixmap(pixmap)

        # 5. Attach to the QLabel and request a repaint
        self.setPixmap(pixmap)
        self.resize(pixmap.size())
        self.update()

    def _scale_portrait_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """
        根据指定屏幕编号（portrait_screen）来计算立绘高度，
        若编号无效则回退为 primaryScreen。
        """

        # 读取配置中的屏幕编号（默认 0 = 主屏）
        screen_index = get_config("./config.json")["screen_index"]

        # 获取所有屏幕
        screens = QGuiApplication.screens()

        # 根据编号选择屏幕（越界自动回退到主屏）
        if 0 <= screen_index < len(screens):
            screen = screens[screen_index]
        else:
            screen = QGuiApplication.primaryScreen()

        # 获取目标屏幕可用高度
        available_height = screen.availableGeometry().height() if screen else None

        # 按屏幕高度缩放
        if available_height:
            target_height = int(available_height * DEFAULT_PORTRAIT_SCREEN_RATIO)
        else:
            target_height = pixmap.height()

        target_height = max(1, target_height)
        target_height = min(target_height, pixmap.height())

        if pixmap.height() >= 240:
            target_height = max(240, target_height)

        # 计算文本缩放
        scale_factor = target_height / max(1, pixmap.height())
        self._current_scale = max(scale_factor, 0.1)
        self._update_text_scaling()

        return pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)

    def _update_text_scaling(self):

        scale = max(self._current_scale, 0.1)
        scaled_font_size = max(10, int(round(self._base_font_size * scale)))
        self.text_font = QFont(self._font_family, scaled_font_size)

        self.text_x_offset = max(10, int(round(self._base_text_x_offset * scale)))
        scaled_y = int(round(self._base_text_y_offset * scale))
        self.text_y_offset = scaled_y if scaled_y < -10 else -10

        self.border_size = max(1, int(round(self._base_border_size * scale)))

    # 显示文本及打字机效果
    def show_text(self, text, typing=True):
        wrapped_text = wrap_text(text)
        self.full_text = wrapped_text  # 设置全部字符
        self.typing_prefix = f"【{self.pet_name}】\n"  # 设置名字格式
        self.index = 0

        def _typing_step():  # 打字机效果
            if self.index < len(self.full_text):
                self.display_text = (
                    self.typing_prefix + self.full_text[: self.index + 1]
                )
                self.index += 1
                self.update()
            else:
                self.typing_timer.stop()

        try:
            self.typing_timer.timeout.disconnect()
        except TypeError:
            pass
        self.typing_timer.timeout.connect(_typing_step)

        if typing:
            self.display_text = self.typing_prefix
            self.typing_timer.start(40)
        else:
            self.display_text = self.typing_prefix + text
            self.update()

    # 输入法候选框定位
    def inputMethodQuery(self, query):
        if query in (Qt.ImMicroFocus, Qt.ImCursorRectangle):
            r = self.rect()

            # 计算出文字显示的区域（和 paintEvent 里绘制对白的位置保持一致）
            text_rect = QRect(
                r.x() + self.text_x_offset,
                r.y() + self.text_y_offset,
                max(1, r.width() - 2 * self.text_x_offset),
                max(1, r.height() // 2 - self.text_y_offset),
            )

            fm = QFontMetrics(self.text_font)
            text = self.display_text or ""

            # 取“最后一行”来估算插入点
            last_line = text.split("\n")[-1]
            w_last = fm.horizontalAdvance(last_line)

            # 光标 x 放在最后一行末尾，但不要超出文字区域
            x = text_rect.x() + min(max(0, w_last), max(1, text_rect.width() - 1))
            # 光标 y 放在文字区域底部一行的基线位置
            y = text_rect.bottom() - fm.height()

            caret = QRect(int(x), int(y), 1, fm.height())

            # 夹在控件内部，避免非法矩形导致 IME 崩溃
            caret = caret.intersected(self.rect().adjusted(0, 0, -1, -1))
            if not caret.isValid():
                # 兜底：放在文字区域左下角
                caret = QRect(
                    text_rect.x(),
                    text_rect.bottom() - fm.height(),
                    1,
                    fm.height(),
                )

            return caret

        return super().inputMethodQuery(query)

    # 输入法事件（中文拼音输入）
    def inputMethodEvent(self, event):
        if self.input_mode:  # 只在输入模式下处理
            commit = event.commitString()  # 确认输入
            preedit = event.preeditString()  # 预编辑（拼音/候选未确认）
            if commit:
                self.input_buffer += commit
            self.preedit_text = preedit
            wrapped = wrap_text(self.input_buffer + self.preedit_text)
            self.display_text = f"【{self.user_name}】\n  「{wrapped or '...'}」"
            self.update()
        else:
            super().inputMethodEvent(event)

    # 键盘事件
    def keyPressEvent(self, event):
        if not self.input_mode:
            # 如果没进入输入模式，交给父类 QLabel 处理
            return super().keyPressEvent(event)

        # ================== 输入模式下 ==================
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            text = self.input_buffer.strip()
            self.input_mode = False
            if text:
                self.display_text = f"【{self.pet_name}】\n"
                self.update()
                # 启动 AI 线程
                self.start_thread(text, role="user")
            else:
                self.show_text("主人，你说什么？", typing=True)

        elif event.key() == Qt.Key_Backspace:
            # 如果有拼音候选框，不删（交给输入法处理）
            if self.preedit_text:
                pass
            else:
                # 删除最后一个字符
                self.input_buffer = self.input_buffer[:-1]
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"【{self.pet_name}】\n  「{wrapped or '...'}」"
                self.update()

        else:
            # 处理英文/数字直接输入
            ch = event.text()
            if ch and not self.preedit_text:
                self.input_buffer += ch
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"【{self.pet_name}】\n  「{wrapped or '...'}」"
                self.update()

    def cleer_history(self):
        self.history = []
        self.portrait_history = []
        self.portrait_history.append(("", str(self.first_portrait)))
        self.update_portrait(f"ムラサメ{portrait_type}", self.first_portrait)
        self._save_history()

    def _load_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print(f"[AIpet] 创建记忆目录失败: {exc}")
            return
        if not self.history_file.exists():
            return
        try:
            with self.history_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as exc:
            print(f"[AIpet] 读取记忆失败: {exc}")
            return
        history = data.get("history")
        portrait_history = data.get("portrait_history")
        if isinstance(history, list):
            self.history = history
        if isinstance(portrait_history, list):
            self.portrait_history = portrait_history

    def _save_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "history": self.history,
                "portrait_history": self.portrait_history,
            }
            with self.history_file.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[AIpet] 保存记忆失败: {exc}")
