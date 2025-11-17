import json
import os
import textwrap
import wave
import shutil
from datetime import datetime
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
from tool.chat import ollama_qwen25vl, ollama_qwen3_image_thinker
from tool.cloud_API_chat import cloud_image_thinker, cloud_vl
from tool.generate import generate_fgimage


def wrap_text(s, width=10):
    return '\n'.join(textwrap.wrap(s, width=width, break_long_words=True, break_on_hyphens=False))

CONFIG = get_config("./config.json")
portrait_type = CONFIG['portrait']
model_type = CONFIG['model_type']
screen_type = CONFIG.get("screen_type", "true")
DEFAULT_PORTRAIT_SCREEN_RATIO = CONFIG['DEFAULT_PORTRAIT_SCREEN_RATIO']

class Murasame(QLabel):
    #鍒濆鍖?
    def __init__(self):
        super().__init__()
        #鏂囧瓧
        self.full_text = ""  #鎵撳瓧鏈烘晥鏋滅敤鍒扮殑鏁翠綋瀛楃涓?
        self.pet_name = "涓涢洦" #瀹犵墿鍚嶇О
        self.user_name = CONFIG["user_name"] #鐢ㄦ埛鍚嶅瓧
        self.display_text = "" #灏嗚灞曠ず鐨勬枃鏈?
        self._font_family = "鎬濇簮榛戜綋Bold.otf"
        self._base_font_size = 40
        self._base_text_x_offset = 140  #鏂囨湰妗嗗乏鍙冲亸绉婚噺
        self._base_text_y_offset = -100 #鏂囨湰妗嗕笂涓嬪亸绉婚噺
        self._base_border_size = 2
        self._current_scale = 1.0
        self.border_size = self._base_border_size
        self._update_text_scaling()

        #鍒涘缓鎵撳瓧鏈烘晥鏋滅殑璁℃椂鍣?
        self.typing_timer = QTimer(self)
        self.typing_speed = 40
        self.typing_timer.setInterval(self.typing_speed)  # 姣?40 姣瑙﹀彂涓€娆★紙鎵撳瓧鏈洪€熷害锛?

        #杈撳叆娉?
        self.input_mode = False  # 鏄惁澶勪簬杈撳叆妯″紡
        self.input_buffer = ""   # 杈撳叆妯″紡涓嬪凡纭鐨勬枃瀛?
        self.preedit_text = ""   # 杈撳叆妯″紡涓嬬殑鎷奸煶/鍊欓€?
        self.setFocusPolicy(Qt.StrongFocus)  # 鎺ユ敹閿洏鐒︾偣
        self.setAttribute(Qt.WA_InputMethodEnabled, True)  # 寮€鍚緭鍏ユ硶鏀寔
        self.setFocus()
        #榧犳爣浜嬩欢
        self.touch_head = False  # 鏄惁姝ｅ湪鎽稿ご锛堝乏閿偣澶撮儴鍚庤繘鍏ュ垽瀹氾級
        self.head_press_x = None # 鎸変笅澶撮儴鏃剁殑妯潗鏍囷紝鐢ㄦ潵鍒ゆ柇鏄惁鈥滄檭鍔ㄢ€?
        self.offset = None       # 涓敭鎷栧姩鏃惰褰曠殑鍋忕Щ閲?

        #AI瀵硅瘽
        self.history = []
        self.portrait_history = []
        self.screen_history = ["", ""]
        self.history_file = Path("./data/history.json")
        self._load_history()

        #鍒濆绔嬬粯
        self.setWindowFlags(
        Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)  # Qt.FramelessWindowHint鍘绘帀鏍囬鏍忓拰杈规锛?Qt.WindowStaysOnTopHint绐楀彛鎬诲湪鏈€鍓嶉潰 锛孮t.Tool宸ュ叿绐楀彛锛堝湪浠诲姟鏍忎笉鍗曠嫭鏄剧ず鍥炬爣锛?
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 璁╂暣涓獥鍙ｆ敮鎸侀€忔槑鍖哄煙銆?
        if portrait_type == "a":
            self.first_portrait = [1950, 1368, 1958]
        elif portrait_type == "b":
            self.first_portrait = [1715, 1306, 1719]
        self.update_portrait(f"銉犮儵銈点儭{portrait_type}", self.first_portrait)
        if not self.portrait_history:
            self.portrait_history.append(("", str(self.first_portrait)))
            self._save_history()

        #绾跨▼
        self.worker = None
        self.interval = CONFIG["screen_interval"]
        self._screenshot_worker = None
        self._screenshot_executor = ThreadPoolExecutor(max_workers=1)  # 澶勭悊灞忓箷鎴浘缃戠粶璋冪敤
        self.force_stop = False  # 鏄惁澶勪簬寮哄埗涓柇鐘舵€?
        if screen_type == "true":
            QTimer.singleShot(1000, lambda: self.start_screenshot_worker(interval=self.interval))

    def focusInEvent(self, event):
        """褰撴瀹犺幏寰楃劍鐐规椂锛堢敤鎴风偣涓€佸紑濮嬭緭鍏ワ級"""
        self.pause_all_ai()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """褰撴瀹犲け鍘荤劍鐐规椂锛堢敤鎴风偣鍑诲埆澶勩€佽緭鍏ョ粨鏉燂級"""
        self.resume_all_ai()
        super().focusOutEvent(event)

    def start_screenshot_worker(self, interval):
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
        # 鎸佷箙鍖栧綋鍓嶅紑鍏崇姸鎬侊紝淇濊瘉鍗充娇鐩存帴鍏抽棴鍛戒护琛屼篃鑳戒繚鐣欒缃?
        try:
            config = get_config("./config.json")
            config["screen_type"] = screen_type
            with open("./config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AIpet] 淇濆瓨 screen_type 澶辫触: {e}")

        if enabled:
            if not (self._screenshot_worker and self._screenshot_worker.isRunning()):
                print("[AIpet] 鍚敤鎴浘绾跨▼")
                self.start_screenshot_worker(interval=self.interval)
        else:
            print("[AIpet] 鍋滅敤鎴浘绾跨▼")
            self.stop_screenshot_worker()

    def is_screenshot_enabled(self) -> bool:
        return screen_type == "true"

    def on_screenshot_captured(self, image_path):
        model_type = get_config("./config.json")["model_type"]
        def task(path):
            try:
                try:
                    if model_type == "deepseek" or model_type == "qwen":
                        if self.force_stop: print("[cloud-vl] 宸蹭腑鏂敓鎴愩€?);return
                        desc = cloud_vl(path)
                    elif model_type == "local":
                        if self.force_stop: print("[ollama-qwen2.5vl] 宸蹭腑鏂敓鎴愩€?);return
                        desc = ollama_qwen25vl(path)
                    propmt = f"绯荤粺鎻愮ず锛氫笅闈㈡槸涓€娈靛鐢ㄦ埛褰撳墠灞忓箷鍐呭鍜屾鍦ㄥ仛鐨勪簨鐨勬弿杩般€傝浣犱互鈥滀笡闆ㄢ€濈殑韬唤鍥炲鍚堥€傜殑璇濄€傚睆骞曟弿杩皗desc}"
                    if self.force_stop: print("灞忓箷鍥炲 宸蹭腑鏂敓鎴愩€?);return
                    self.start_thread(propmt, role="system", t=True)
                except Exception as e:
                    print(f"[AIpet] 鎴浘鍒嗘瀽澶辫触: {e}")
            finally:
                try:
                    os.remove(path)
                except:
                    pass
        self._screenshot_executor.submit(task, image_path)

    def pause_all_ai(self):
        """鐢ㄦ埛杈撳叆鏃讹細鍋滄鎴浘绾跨▼銆佷腑鏂瑼I鏄剧ず涓庤闊?""
        self.force_stop = True  # 鉁?鍚敤杞腑鏂爣蹇?

        if self._screenshot_worker and self._screenshot_worker.isRunning():
            print("[AIpet] 鏆傚仠鎴浘绾跨▼")
            self.stop_screenshot_worker()
        if self.worker and self.worker.isRunning():
            self.worker.stop_screen()
        try:
            QSound.stop()
        except Exception:
            pass

    def resume_all_ai(self):
        """鐢ㄦ埛杈撳叆缁撴潫鍚庯細鎭㈠鎴浘绾跨▼涓嶢I鍝嶅簲"""
        self.force_stop = False  # 鉁?瑙ｉ櫎杞腑鏂爣蹇?
        if not (self._screenshot_worker and self._screenshot_worker.isRunning()) and screen_type == "true":
            print("[AIpet] 鎭㈠鎴浘绾跨▼")
            self.start_screenshot_worker(interval=self.interval)

    #qwen3绾跨▼鐨勬Ы鍑芥暟
    def on_reply(self, reply, portrait_list, history, portrait_history, voices):
        self.portrait_history = portrait_history
        self.history = history
        self._save_history()
        def show_next_sentence(index = 0):
            def get_audio_length_wave(audio_file_path):
                try:
                    with wave.open(audio_file_path, 'rb') as wave_file:
                        frames = wave_file.getnframes()  # 鑾峰彇闊抽鐨勫抚鏁?
                        rate = wave_file.getframerate()  # 鑾峰彇闊抽鐨勫抚閫熺巼
                        duration = frames / float(rate)  # 璁＄畻鏃堕暱锛堢锛?
                        return duration * 1000  # 杞崲涓烘绉?
                except Exception:
                    return 0

            if index >= len(reply):
                return
            sentence = reply[index]
            portrait = portrait_list[index]
            self.update_portrait(f"銉犮儵銈点儭{portrait_type}", portrait)
            voice_id = voices[index]
            voice_path = f"./voices/{voice_id}.wav" if voice_id else None
            voice_length = 0
            if voice_path and os.path.exists(voice_path):
                voice_length = get_audio_length_wave(os.path.abspath(voice_path))
                if voice_length > 0:
                    QSound.play(voice_path)
            self.show_text(sentence, typing=True)
            # 璁＄畻鎵撳瓧鏈洪渶瑕佺殑鏃堕棿锛?0ms * 姣忎釜瀛楋級
            delay = max(40 * len(sentence) + 800, voice_length + 400)  # 棰濆鍔?0.8 绉掑仠椤?
            if voice_path and os.path.exists(voice_path) and voice_length > 0:
                QTimer.singleShot(int(delay), lambda: [os.remove(voice_path), show_next_sentence(index + 1)])
            else:
                QTimer.singleShot(int(delay), lambda: show_next_sentence(index + 1))

        show_next_sentence(index=0)
        self.worker = None  # 绾跨▼缁撴潫鍚庢竻绌哄紩鐢?


    # 鍚姩涓€涓柊绾跨▼锛堝畨鍏ㄧ増锛?鎵撴柇鏃х嚎绋?
    def start_thread(self, text, role, t = False):
        # 缁撴潫鏃х嚎绋?
        if self.worker and self.worker.isRunning():
            self.worker.stop_all()  # 鉁?閫氱煡绾跨▼涓柇
            self.worker.wait(1000)

        # 鍚姩鏂扮嚎绋?
        if model_type == "local":
            self.worker = qwen3_lora_Worker(self.history, self.portrait_history, text, role, t=t)
        else:
            self.worker = cloud_API_Worker(self.history, self.portrait_history, text, role, t=t)

        self.worker.finished.connect(self.on_reply)
        self.worker.start()

    #榧犳爣鎸変笅浜嬩欢
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 鍒ゆ柇鐐瑰湪鍝噷
            if event.y() < 150:  # 澶撮儴鍖哄煙
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:  # 涓嬪崐韬尯鍩?鈫?杈撳叆妯″紡
                self.input_mode = True
                self.input_buffer = ""
                self.preedit_text = ""
                self.display_text = f"銆恵self.user_name}銆慭n  ..."
                self.update()
            else:
                # 鍏朵粬鍦版柟锛屼粈涔堜篃涓嶅仛
                self.touch_head = False
                self.head_press_x = None
                self.setCursor(Qt.ArrowCursor)

        elif event.button() == Qt.MiddleButton:
            # 涓敭鎷栧姩
            self.offset = event.pos()
            self.setCursor(Qt.SizeAllCursor)

    #榧犳爣绉诲姩浜嬩欢
    def mouseMoveEvent(self, event):
        # 鍒ゆ柇鏄笉鏄湪鈥滄懜澶粹€?
        if self.touch_head and self.head_press_x is not None:
            if abs(event.x() - self.head_press_x) > 50:
                self.start_thread("涓讳汉鎽镐簡鎽镐綘鐨勫ご", role="system")
                self.touch_head = False

        # 涓敭鎷栧姩绐楀彛
        if self.offset is not None and event.buttons() == Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.offset)

    #榧犳爣閲婃斁浜嬩欢
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)  # 鎭㈠绠ご

        elif event.button() == Qt.MiddleButton:
            self.offset = None
            self.setCursor(Qt.ArrowCursor)  # 鎷栧姩缁撴潫涔熻鎭㈠绠ご

    #缁樺埗浜嬩欢
    def paintEvent(self, event):
        # 1. 鍏堣皟鐢?QLabel 榛樿鐨勭粯鍒讹紙鐢荤珛缁?鑳屾櫙锛?
        super().paintEvent(event)  #璋冪敤杩欎釜灏变細鑷姩缁樺埗鐜板湪椤圭洰閲屽啓杩囩殑self.setPixmap

        # 2. 鍐嶅彔鍔犵粯鍒舵枃瀛?
        if self.display_text:  #==True   杩囨护鎺夌┖瀛楃涓?"鍜孨one
            #璁剧疆缁樺浘鐜
            painter = QPainter(self) #鍒涘缓涓€涓?QPainter 瀵硅薄锛岀洰鏍囨槸 鍦ㄨ繖涓帶浠?(self锛屼篃灏辨槸 QLabel 瀛愮被) 涓婄粯鍒?
            painter.setRenderHint(QPainter.Antialiasing, True) #寮€鍚?鎶楅敮榻匡紙鍥惧舰骞虫粦澶勭悊锛?
            painter.setRenderHint(QPainter.TextAntialiasing, True) #寮€鍚?鏂囧瓧鎶楅敮榻?
            painter.setFont(self.text_font) #璁剧疆鎺ヤ笅鏉ョ粯鍒舵枃瀛楁椂鐢ㄧ殑瀛椾綋

            rect = self.rect() #鑾峰彇绐楀彛鏁版嵁
            # 璋冩暣鏂囧瓧鍖哄煙锛堟斁鍦ㄧ珛缁樹笂鍗婇儴鍒嗭級
            text_rect = rect.adjusted(#(left, top, right, bottom) 杩斿洖涓€涓柊鐨勭煩褰紝骞跺姞涓婂亸绉婚噺
                self.text_x_offset,   #宸﹁竟鐣?鍋忕Щ閲?
                self.text_y_offset,   #涓婅竟鐣?鍋忕Щ閲?
                -self.text_x_offset,  #鍙宠竟鐣?鍋忕Щ閲?
                -rect.height()//2 + self.text_y_offset#涓嬭竟鐣?绐楀彛楂樺害鐨勪竴鍗婏紝鍐?鍋忕Щ閲忋€傛剰鍛崇潃涓嬭竟鐣屾槸绐楀彛涓婂崐閮ㄥ垎杩樿涓婁竴涓亸绉婚噺
            )

            # 濡傛灉鏈夋崲琛屽氨闈犲乏瀵归綈锛屽惁鍒欏眳涓?
            if '\n' in self.display_text:
                align_flag = Qt.AlignLeft | Qt.AlignBottom #宸﹀榻?搴曢儴瀵归綈
            else:
                align_flag = Qt.AlignHCenter | Qt.AlignBottom #姘村钩灞呬腑+搴曢儴瀵归綈

            # 鏂囧瓧鎻忚竟锛堥粦鑹诧級
            border_size = self.border_size  #鎻忚竟鐨勫亸绉婚噺
            painter.setPen(QColor(44, 22, 28)) #璁剧疆鐢荤瑪棰滆壊RGB 娣辨鑹?
            for dx, dy in [   #鍒嗗埆鍚戝叓涓柟鍚戝亸绉荤粯鍒跺叓涓瓧浣擄紝褰㈡垚鎻忚竟
                (-border_size, 0), (border_size, 0),    #宸︺€佸彸
                (0, -border_size), (0, border_size),    #涓娿€佷笅
                (border_size, -border_size), (border_size, border_size),    #鍙充笂銆佸彸涓?
                (-border_size, -border_size), (-border_size, border_size)   #宸︿笂銆佸乏涓?
            ]:
                painter.drawText(  #缁樺埗鏂囧瓧
                    text_rect.translated(dx, dy),#杩斿洖涓€涓柊鐨勭煩褰紝鍩轰簬鍘熺煩褰㈣繘琛屾暣浣撳钩绉?
                    align_flag,   #瀵归綈鏂瑰紡
                    self.display_text  #瑕佹樉绀虹殑瀛椾綋
                )

            # 鏂囧瓧姝ｄ綋锛堢櫧鑹诧級
            painter.setPen(Qt.white)  #=Qcolor("white")
            painter.drawText(text_rect, align_flag, self.display_text)

            painter.end()

    #鏇存柊绔嬬粯
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

    #鏄剧ず鏂囨湰鍙婃墦瀛楁満鏁堟灉
    def show_text(self, text, typing=True):
        wrapped_text = wrap_text(text)
        self.full_text = wrapped_text  # 璁剧疆鍏ㄩ儴瀛楃
        self.typing_prefix = f"銆恵self.pet_name}銆慭n"  #璁剧疆鍚嶅瓧鏍煎紡
        self.index = 0
        def _typing_step():#鎵撳瓧鏈烘晥鏋?
            if self.index < len(self.full_text):
                self.display_text = self.typing_prefix + self.full_text[:self.index + 1]#鍚嶅瓧鍔犱笂浠庡畬鏁村瓧绗︿覆寮€澶村彇鐨勫瓧绗?
                self.index += 1
                self.update()
            else:
                self.typing_timer.stop()
        try:
            self.typing_timer.timeout.disconnect()
        except TypeError:
            pass
        self.typing_timer.timeout.connect(_typing_step)#璁℃椂鍣ㄧ粦瀹?

        if typing: #妫€娴嬫槸鍚﹂渶瑕佹墦瀛楁満鏁堟灉
            self.display_text = self.typing_prefix#濡傛灉闇€瑕佸氨灏嗙幇鍦ㄥ睍绀虹殑瀛楃涓插垵濮嬩负鍚嶅瓧锛岃繖鏍峰彧鏈夊悗缁枃鏈墠鏈夋墦瀛楁満鏁堟灉
            self.typing_timer.start(40)
        else:
            self.display_text = self.typing_prefix + text#濡傛灉涓嶉渶瑕佸氨涓€娆℃€ф樉绀?
            self.update()

    #杈撳叆娉曞€欓€夋瀹氫綅
    def inputMethodQuery(self, query):
        if query in (Qt.ImMicroFocus, Qt.ImCursorRectangle):
            r = self.rect()

            # 璁＄畻鍑烘枃瀛楁樉绀虹殑鍖哄煙锛堝拰浣犲湪 paintEvent 閲岀粯鍒跺鐧界殑浣嶇疆淇濇寔涓€鑷达級
            text_rect = QRect(
                r.x() + self.text_x_offset,
                r.y() + self.text_y_offset,
                max(1, r.width() - 2 * self.text_x_offset),
                max(1, r.height() // 2 - self.text_y_offset)
            )

            fm = QFontMetrics(self.text_font)
            text = self.display_text or ""

            # 鍙栤€滄渶鍚庝竴琛屸€濇潵浼扮畻鎻掑叆鐐癸紙鏇存帴杩戠湡瀹炶緭鍏ヤ綅缃級
            last_line = text.split('\n')[-1]
            w_last = fm.horizontalAdvance(last_line)

            # 鍏夋爣 x 鏀惧湪鏈€鍚庝竴琛屾湯灏撅紝浣嗕笉瑕佽秴鍑烘枃瀛楀尯鍩?
            x = text_rect.x() + min(max(0, w_last), max(1, text_rect.width() - 1))
            # 鍏夋爣 y 鏀惧湪鏂囧瓧鍖哄煙搴曢儴涓€琛岀殑鍩虹嚎浣嶇疆
            y = text_rect.bottom() - fm.height()

            caret = QRect(int(x), int(y), 1, fm.height())

            # 澶瑰湪鎺т欢鍐呴儴锛岄伩鍏嶉潪娉曠煩褰㈠鑷?IME 宕╂簝
            caret = caret.intersected(self.rect().adjusted(0, 0, -1, -1))
            if not caret.isValid():
                # 鍏滃簳锛氭斁鍦ㄦ枃瀛楀尯鍩熷乏涓嬭
                caret = QRect(text_rect.x(), text_rect.bottom() - fm.height(), 1, fm.height())

            return caret

        return super().inputMethodQuery(query)

    # 杈撳叆娉曚簨浠讹紙涓枃鎷奸煶杈撳叆锛?
    def inputMethodEvent(self, event):
        if self.input_mode:  # 鍙湪杈撳叆妯″紡涓嬪鐞?
            commit = event.commitString()  # 纭杈撳叆锛堝€欓€夐€変腑鐨勬眽瀛楋級
            preedit = event.preeditString()  # 棰勭紪杈戯紙鎷奸煶/鍊欓€夋湭纭锛?
            if commit:
                self.input_buffer += commit
            self.preedit_text = preedit
            wrapped = wrap_text(self.input_buffer + self.preedit_text)
            self.display_text = f"銆恵self.user_name}銆慭n  銆寋wrapped or '...'}銆?
            self.update()
        else:
            super().inputMethodEvent(event)

    #閿洏浜嬩欢
    def keyPressEvent(self, event):
        if not self.input_mode:
            # 濡傛灉娌¤繘鍏ヨ緭鍏ユā寮忥紝浜ょ粰鐖剁被 QLabel 澶勭悊
            return super().keyPressEvent(event)

        # ================== 杈撳叆妯″紡涓?==================
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            text = self.input_buffer.strip()
            self.input_mode = False
            if text:
                self.display_text = f"銆恵self.pet_name}銆慭n"
                self.update()
                # 鍚姩AI绾跨▼
                self.start_thread(text, role="user")
            else:
                self.show_text("涓讳汉锛屼綘璇翠粈涔堬紵", typing=True)


        elif event.key() == Qt.Key_Backspace:
            # 濡傛灉鏈夋嫾闊冲€欓€夋锛屼笉鍒狅紙浜ょ粰杈撳叆娉曞鐞嗭級
            if self.preedit_text:
                pass
            else:
                # 鍒犻櫎鏈€鍚庝竴涓瓧绗?
                self.input_buffer = self.input_buffer[:-1]
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"銆恵self.pet_name}銆慭n  銆寋wrapped or '...'}銆?
                self.update()

        else:
            # 澶勭悊鑻辨枃/鏁板瓧鐩存帴杈撳叆
            ch = event.text()
            if ch and not self.preedit_text:
                self.input_buffer += ch
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"銆恵self.pet_name}銆慭n  銆寋wrapped or '...'}銆?
                self.update()

    def cleer_history(self):
        self.history = []
        self.portrait_history = []
        self.portrait_history.append(("", str(self.first_portrait)))
        self.update_portrait(f"銉犮儵銈点儭{portrait_type}", self.first_portrait)
        self._save_history()

    def _load_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print(f"[AIpet] 鍒涘缓璁板繂鐩綍澶辫触: {exc}")
            return
        if not self.history_file.exists():
            return
        try:
            with self.history_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as exc:
            print(f"[AIpet] 璇诲彇璁板繂澶辫触: {exc}")
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
            print(f"[AIpet] 淇濆瓨璁板繂澶辫触: {exc}")

