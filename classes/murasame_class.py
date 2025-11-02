import json
import os
import textwrap
import wave
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
from classes.Worker_class import qwen3_lora_Worker, qwen3_lora_deepseekAPI_Worker
from tool import get_config
from tool import ollama_qwen25vl, ollama_qwen3_image_thinker, deepseek_image_thinker
from tool.generate import generate_fgimage


def wrap_text(s, width=10):
    return '\n'.join(textwrap.wrap(s, width=width, break_long_words=True, break_on_hyphens=False))

CONFIG = get_config("./config.json")
portrait_type = CONFIG['portrait']
model_type = CONFIG['model_type']
screen_type = CONFIG['screen_type']
DEFAULT_PORTRAIT_SCREEN_RATIO = CONFIG['DEFAULT_PORTRAIT_SCREEN_RATIO']

class Murasame(QLabel):
    #初始化
    def __init__(self):
        super().__init__()
        #文字
        self.full_text = ""  #打字机效果用到的整体字符串
        self.pet_name = "丛雨" #宠物名称
        self.user_name = CONFIG["user_name"] #用户名字
        self.display_text = "" #将要展示的文本
        self._font_family = "思源黑体Bold.otf"
        self._base_font_size = 40
        self._base_text_x_offset = 140  #文本框左右偏移量
        self._base_text_y_offset = -100 #文本框上下偏移量
        self._base_border_size = 2
        self._current_scale = 1.0
        self.border_size = self._base_border_size
        self._update_text_scaling()

        #创建打字机效果的计时器
        self.typing_timer = QTimer(self)
        self.typing_speed = 40
        self.typing_timer.setInterval(self.typing_speed)  # 每 40 毫秒触发一次（打字机速度）

        #输入法
        self.input_mode = False  # 是否处于输入模式
        self.input_buffer = ""   # 输入模式下已确认的文字
        self.preedit_text = ""   # 输入模式下的拼音/候选
        self.setFocusPolicy(Qt.StrongFocus)  # 接收键盘焦点
        self.setAttribute(Qt.WA_InputMethodEnabled, True)  # 开启输入法支持
        self.setFocus()
        #鼠标事件
        self.touch_head = False  # 是否正在摸头（左键点头部后进入判定）
        self.head_press_x = None # 按下头部时的横坐标，用来判断是否“晃动”
        self.offset = None       # 中键拖动时记录的偏移量

        #AI对话
        self.history = []
        self.portrait_history = []
        self.screen_history = ["", ""]
        self.history_file = Path("./data/history.json")
        self._load_history()

        #初始立绘
        self.setWindowFlags(
        Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)  # Qt.FramelessWindowHint去掉标题栏和边框， Qt.WindowStaysOnTopHint窗口总在最前面 ，Qt.Tool工具窗口（在任务栏不单独显示图标）
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 让整个窗口支持透明区域。
        if portrait_type == "a":
            self.first_portrait = [1950, 1368, 1958]
        elif portrait_type == "b":
            self.first_portrait = [1715, 1306, 1719]
        self.update_portrait(f"ムラサメ{portrait_type}", self.first_portrait)
        if not self.portrait_history:
            self.portrait_history.append(("", str(self.first_portrait)))
            self._save_history()

        #线程
        self.worker = None
        self.interval = 30
        self._screenshot_worker = None
        self._screenshot_executor = ThreadPoolExecutor(max_workers=2)  # 处理网络调用用
        self.force_stop = False  # 是否处于强制中断状态
        if screen_type == "true":
            QTimer.singleShot(1000, lambda: self.start_screenshot_worker(interval=self.interval))


    def start_screenshot_worker(self, interval=3.0):
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

    def on_screenshot_captured(self, image_path):
        def task(path):
            try:
                try:
                    if self.force_stop:print("[ollama-qwen2.5vl] 已中断生成。");return
                    desc = ollama_qwen25vl(path)
                    if self.force_stop:print("[image_thinker] 已中断生成。");return
                    if model_type == "deepseek":
                        thinker_reply, self.screen_history = deepseek_image_thinker(self.screen_history, desc)
                    elif model_type == "local":
                        thinker_reply, self.screen_history = ollama_qwen3_image_thinker(self.screen_history, desc)
                    if "null" not in thinker_reply:
                        self.start_qwen3_thread(thinker_reply, role="system", t=True)
                except Exception as e:
                    print(f"[AIpet] 截图分析失败: {e}")
            finally:
                try:
                    os.remove(path)
                except:
                    pass

        self._screenshot_executor.submit(task, image_path)

    def pause_all_ai(self):
        """用户输入时：停止截图线程、中断AI显示与语音"""
        self.force_stop = True  # ✅ 启用软中断标志

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
        """用户输入结束后：恢复截图线程与AI响应"""
        self.force_stop = False  # ✅ 解除软中断标志
        if not (self._screenshot_worker and self._screenshot_worker.isRunning()) and screen_type == "true":
            print("[AIpet] 恢复截图线程")
            self.start_screenshot_worker(interval=self.interval)

    #qwen3线程的槽函数
    def on_qwen3_reply(self, reply, portrait_list, history, portrait_history, voices):
        self.portrait_history = portrait_history
        self.history = history
        self._save_history()
        def show_next_sentence(index = 0):
            def get_audio_length_wave(audio_file_path):
                with wave.open(audio_file_path, 'rb') as wave_file:
                    frames = wave_file.getnframes()  # 获取音频的帧数
                    rate = wave_file.getframerate()  # 获取音频的帧速率
                    duration = frames / float(rate)  # 计算时长（秒）
                    return duration * 1000  # 转换为毫秒

            if index >= len(reply):
                return
            sentence = reply[index]
            portrait = portrait_list[index]
            self.update_portrait(f"ムラサメ{portrait_type}", portrait)
            voice_path = f"./voices/{voices[index]}.wav"
            voice_length = get_audio_length_wave(os.path.abspath(voice_path))
            QSound.play(voice_path)
            self.show_text(sentence, typing=True)
            # 计算打字机需要的时间（40ms * 每个字）
            delay = max(40 * len(sentence) + 800, voice_length + 400)  # 额外加 0.8 秒停顿
            QTimer.singleShot(int(delay), lambda: [os.remove(voice_path), show_next_sentence(index + 1)])

        show_next_sentence(index=0)
        self.worker = None  # 线程结束后清空引用


    # 启动一个新线程（安全版） 打断旧线程
    def start_qwen3_thread(self, text, role, t = False):
        # 结束旧线程
        if self.worker and self.worker.isRunning():
            self.worker.stop_all()  # ✅ 通知线程中断
            self.worker.wait(1000)

        # 启动新线程
        if model_type == "local":
            self.worker = qwen3_lora_Worker(self.history, self.portrait_history, text, role, t=t)
        elif model_type == "deepseek":
            self.worker = qwen3_lora_deepseekAPI_Worker(self.history, self.portrait_history, text, role, t=t)

        self.worker.finished.connect(self.on_qwen3_reply)
        self.worker.start()

    def focusInEvent(self, event):
        """当桌宠获得焦点时（用户点中、开始输入）"""
        self.pause_all_ai()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """当桌宠失去焦点时（用户点击别处、输入结束）"""
        self.resume_all_ai()
        super().focusOutEvent(event)

    #鼠标按下事件
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 判断点在哪里
            if event.y() < 150:  # 头部区域
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:  # 下半身区域 → 输入模式
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

    #鼠标移动事件
    def mouseMoveEvent(self, event):
        # 判断是不是在“摸头”
        if self.touch_head and self.head_press_x is not None:
            if abs(event.x() - self.head_press_x) > 50:
                self.start_qwen3_thread("主人摸了摸你的头", role="system")
                self.touch_head = False

        # 中键拖动窗口
        if self.offset is not None and event.buttons() == Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.offset)

    #鼠标释放事件
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)  # 恢复箭头

        elif event.button() == Qt.MiddleButton:
            self.offset = None
            self.setCursor(Qt.ArrowCursor)  # 拖动结束也要恢复箭头

    #绘制事件
    def paintEvent(self, event):
        # 1. 先调用 QLabel 默认的绘制（画立绘/背景）
        super().paintEvent(event)  #调用这个就会自动绘制现在项目里写过的self.setPixmap

        # 2. 再叠加绘制文字
        if self.display_text:  #==True   过滤掉空字符串""和None
            #设置绘图环境
            painter = QPainter(self) #创建一个 QPainter 对象，目标是 在这个控件 (self，也就是 QLabel 子类) 上绘制
            painter.setRenderHint(QPainter.Antialiasing, True) #开启 抗锯齿（图形平滑处理）
            painter.setRenderHint(QPainter.TextAntialiasing, True) #开启 文字抗锯齿
            painter.setFont(self.text_font) #设置接下来绘制文字时用的字体

            rect = self.rect() #获取窗口数据
            # 调整文字区域（放在立绘上半部分）
            text_rect = rect.adjusted(#(left, top, right, bottom) 返回一个新的矩形，并加上偏移量
                self.text_x_offset,   #左边界+偏移量
                self.text_y_offset,   #上边界+偏移量
                -self.text_x_offset,  #右边界-偏移量
                -rect.height()//2 + self.text_y_offset#下边界-窗口高度的一半，再+偏移量。意味着下边界是窗口上半部分还要上一个偏移量
            )

            # 如果有换行就靠左对齐，否则居中
            if '\n' in self.display_text:
                align_flag = Qt.AlignLeft | Qt.AlignBottom #左对齐+底部对齐
            else:
                align_flag = Qt.AlignHCenter | Qt.AlignBottom #水平居中+底部对齐

            # 文字描边（黑色）
            border_size = self.border_size  #描边的偏移量
            painter.setPen(QColor(44, 22, 28)) #设置画笔颜色RGB 深棕色
            for dx, dy in [   #分别向八个方向偏移绘制八个字体，形成描边
                (-border_size, 0), (border_size, 0),    #左、右
                (0, -border_size), (0, border_size),    #上、下
                (border_size, -border_size), (border_size, border_size),    #右上、右下
                (-border_size, -border_size), (-border_size, border_size)   #左上、左下
            ]:
                painter.drawText(  #绘制文字
                    text_rect.translated(dx, dy),#返回一个新的矩形，基于原矩形进行整体平移
                    align_flag,   #对齐方式
                    self.display_text  #要显示的字体
                )

            # 文字正体（白色）
            painter.setPen(Qt.white)  #=Qcolor("white")
            painter.drawText(text_rect, align_flag, self.display_text)

            painter.end()

    #更新立绘
    def update_portrait(self, target, layers):
        """Update portrait image by converting numpy RGBA into a QLabel pixmap."""
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
        qimg = QImage(cv_img_bgra.data, w, h, bytes_per_line, QImage.Format_RGBA8888)

        # 4. Convert to QPixmap and apply adaptive scaling
        pixmap = QPixmap.fromImage(qimg)
        pixmap = self._scale_portrait_pixmap(pixmap)

        # 5. Attach to the QLabel and request a repaint
        self.setPixmap(pixmap)
        self.resize(pixmap.size())
        self.update()

    def _scale_portrait_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """Scale portrait height proportionally to the current screen."""
        screen = QGuiApplication.primaryScreen()
        available_height = screen.availableGeometry().height() if screen else None

        if available_height:
            target_height = int(available_height * DEFAULT_PORTRAIT_SCREEN_RATIO)
        else:
            target_height = pixmap.height()

        target_height = max(1, target_height)
        target_height = min(target_height, pixmap.height())
        if pixmap.height() >= 240:
            target_height = max(240, target_height)

        scale_factor = target_height / max(1, pixmap.height())
        self._current_scale = max(scale_factor, 0.1)
        self._update_text_scaling()

        return pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)

    def _update_text_scaling(self):
        """Adjust subtitle font, margins, and outlines to follow portrait scale."""
        scale = max(self._current_scale, 0.1)
        scaled_font_size = max(10, int(round(self._base_font_size * scale)))
        self.text_font = QFont(self._font_family, scaled_font_size)

        self.text_x_offset = max(10, int(round(self._base_text_x_offset * scale)))
        scaled_y = int(round(self._base_text_y_offset * scale))
        self.text_y_offset = scaled_y if scaled_y < -10 else -10

        self.border_size = max(1, int(round(self._base_border_size * scale)))

    #显示文本及打字机效果
    def show_text(self, text, typing=True):
        wrapped_text = wrap_text(text)
        self.full_text = wrapped_text  # 设置全部字符
        self.typing_prefix = f"【{self.pet_name}】\n"  #设置名字格式
        self.index = 0
        def _typing_step():#打字机效果
            if self.index < len(self.full_text):
                self.display_text = self.typing_prefix + self.full_text[:self.index + 1]#名字加上从完整字符串开头取的字符
                self.index += 1
                self.update()
            else:
                self.typing_timer.stop()
        try:
            self.typing_timer.timeout.disconnect()
        except TypeError:
            pass
        self.typing_timer.timeout.connect(_typing_step)#计时器绑定

        if typing: #检测是否需要打字机效果
            self.display_text = self.typing_prefix#如果需要就将现在展示的字符串初始为名字，这样只有后续文本才有打字机效果
            self.typing_timer.start(40)
        else:
            self.display_text = self.typing_prefix + text#如果不需要就一次性显示
            self.update()

    #输入法候选框定位
    def inputMethodQuery(self, query):
        if query in (Qt.ImMicroFocus, Qt.ImCursorRectangle):
            r = self.rect()

            # 计算出文字显示的区域（和你在 paintEvent 里绘制对白的位置保持一致）
            text_rect = QRect(
                r.x() + self.text_x_offset,
                r.y() + self.text_y_offset,
                max(1, r.width() - 2 * self.text_x_offset),
                max(1, r.height() // 2 - self.text_y_offset)
            )

            fm = QFontMetrics(self.text_font)
            text = self.display_text or ""

            # 取“最后一行”来估算插入点（更接近真实输入位置）
            last_line = text.split('\n')[-1]
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
                caret = QRect(text_rect.x(), text_rect.bottom() - fm.height(), 1, fm.height())

            return caret

        return super().inputMethodQuery(query)

    # 输入法事件（中文拼音输入）
    def inputMethodEvent(self, event):
        if self.input_mode:  # 只在输入模式下处理
            commit = event.commitString()  # 确认输入（候选选中的汉字）
            preedit = event.preeditString()  # 预编辑（拼音/候选未确认）
            if commit:
                self.input_buffer += commit
            self.preedit_text = preedit
            wrapped = wrap_text(self.input_buffer + self.preedit_text)
            self.display_text = f"【{self.user_name}】\n  「{wrapped or '...'}」"
            self.update()
        else:
            super().inputMethodEvent(event)

    #键盘事件
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
                # 启动AI线程
                print(f"[User input] {text}")
                self.start_qwen3_thread(text, role="user")
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
