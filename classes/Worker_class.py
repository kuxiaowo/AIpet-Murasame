
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QGuiApplication

from tool import deepseek_portrait, deepseek_translate, deepseek_emotion, deepseek_talk
from tool import get_config
from tool import qwen3_lora, ollama_qwen3_sentence, ollama_qwen3_portrait, gpt_sovits_tts, ollama_qwen3_emotion, \
    ollama_qwen3_translate

portrait_type = get_config("./config.json")['portrait']


class qwen3_lora_Worker(QThread):
    '''将历史与用户信息交给对话模型，然后将回复交给句子分割模型'''
    finished = pyqtSignal(list, list, list, list, list)  # 返回 (AI回复, history)

    def __init__(self, history, portrait_history, user_input, role="user", t = False):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role
        self.t = t
        self.force_stop = False

    def stop_all(self):
        """外部调用，用于请求线程中断"""
        self.force_stop = True

    def stop_screen(self):
        """外部调用，用于请求线程中断"""
        if self.t:
            self.force_stop = True
    def run(self):
        def to_list(text):
            try:
                text = json.loads(text)  # 把字符串解析成 Python 列表
            except Exception as e:
                text = [text]  # 如果解析失败，就退化成单句
            return text
        if self.force_stop:
            print("[qwen3-lora] 已中断生成。")
            return
        print("11")
        reply, history = qwen3_lora(self.history, self.user_input, self.role)  # 对话
        if self.force_stop:print("[ollama-qwn3] 已中断生成。");return
        reply = ollama_qwen3_sentence(reply)  # 句子分割
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        history[-1]["content"] = reply
        portrait_list, portrait_history = ollama_qwen3_portrait(reply, self.portrait_history, portrait_type)  # 立绘
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        emotion_list = ollama_qwen3_emotion(history)  # 情感
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        translate = ollama_qwen3_translate(reply)  # 翻译

        translate = to_list(translate)
        reply = to_list(reply)
        emotion_list = to_list(emotion_list)
        portrait_list = to_list(portrait_list)

        # 并发执行所有TTS任务
        voices = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交所有TTS任务
            tts_futures = []
            for text, emotion in zip(translate, emotion_list):
                if self.force_stop: print("[tts] 已中断生成。");return
                future = executor.submit(gpt_sovits_tts, text, emotion)
                tts_futures.append(future)

            # 按顺序获取结果，保持原顺序
            for future in tts_futures:
                if self.force_stop: print("[tts] 已中断生成。");return
                voices.append(future.result())

        self.finished.emit(reply, portrait_list, history, portrait_history, voices)  # 发回主线程

class qwen3_lora_deepseekAPI_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list)

    def __init__(self, history, portrait_history, user_input, role="user", t = False):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role
        self.force_stop = False
        self.t = t

    def stop_all(self):
        """外部调用，用于请求线程中断"""
        self.force_stop = True
    def stop_screen(self):
        """外部调用，用于请求线程中断"""
        if self.t:
            self.force_stop = True
    '''
    这种定义方法来实现中途中断的操作我之前一直没有想到，这个做法很好
    '''
    def run(self):
        def to_list(text):
            try:
                return json.loads(text)
            except:
                return [text]

        # 1. 先获取对话回复（这个必须串行，因为依赖前面的历史）
        if self.force_stop:print("[deepseek] 已中断生成。");return
        reply, history = deepseek_talk(self.history, self.user_input, self.role)
        '''
        reply = deepseek_sentence(reply)  # 句子分割
        history[-1]["content"] = reply
        '''
        # 2. 使用线程池并发执行所有 DeepSeek 任务和 TTS 任务
        if self.force_stop:print("[deepseek] 已中断生成。");return
        with ThreadPoolExecutor(max_workers=5) as executor:  # 增加线程数
            # 提交所有任务
            future_portrait = executor.submit(deepseek_portrait, reply, self.portrait_history, portrait_type)
            future_emotion = executor.submit(deepseek_emotion, history)
            future_translate = executor.submit(deepseek_translate, reply)

            # 获取所有结果
            portrait_result, portrait_history = future_portrait.result()
            emotion_result = future_emotion.result()
            translate_result = future_translate.result()

        # 3. 处理结果

        translate_list = to_list(translate_result)
        emotion_list = to_list(emotion_result)
        portrait_list = to_list(portrait_result)
        reply_list = to_list(reply)
        # 4. 并发执行所有TTS任务
        voices = []
        with ThreadPoolExecutor(max_workers=3) as tts_executor:
            # 提交所有TTS任务
            tts_futures = []
            for text, emotion in zip(translate_list, emotion_list):
                if self.force_stop:print("[tts] 已中断生成。");return
                future = tts_executor.submit(gpt_sovits_tts, text, emotion)
                tts_futures.append(future)

            # 按顺序获取结果，保持原顺序
            for future in tts_futures:
                if self.force_stop:print("[tts] 已中断生成。");return
                voices.append(future.result())

        self.finished.emit(reply_list, portrait_list, history, portrait_history, voices)




class ScreenWorker(QThread):
    # 发出临时文件路径（主线程负责删除）
    screenshot_captured = pyqtSignal(str)

    def __init__(self, interval_sec=3.0, parent=None):
        super().__init__(parent)
        self.interval = interval_sec

    def run(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        while not self.isInterruptionRequested():
            # 抓屏（全屏）
            pixmap = screen.grabWindow(0)
            # 存到临时文件
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_name = tmp.name
            tmp.close()
            pixmap.save(tmp_name, "PNG")
            # 发信号，让主线程去处理（网络调用等）
            self.screenshot_captured.emit(tmp_name)
            # sleep 可被 requestInterruption() 打断（间隔相对宽松）
            for _ in range(int(self.interval * 10)):
                if self.isInterruptionRequested():
                    break
                time.sleep(0.1)
