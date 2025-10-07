import json
from functools import partial

from PyQt5.QtCore import QThread, pyqtSignal
from concurrent.futures import ThreadPoolExecutor
from tool import qwen3_lora, ollama_qwen3_sentence, ollama_qwen3_portrait, gpt_sovits_tts, ollama_qwen3_emotion, ollama_qwen3_translate
from tool import deepseek_portrait, deepseek_translate, deepseek_emotion, deepseek_talk
from tool import get_config

portrait_type = get_config("./config.json")['portrait']
'''
class qwen3_lora_Worker(QThread):
    \'''将历史与用户信息交给对话模型，然后将回复交给句子分割模型\'''
    finished = pyqtSignal(list, list, list, list, list)  # 返回 (AI回复, history)

    def __init__(self, history, portrait_history, user_input, role="user"):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role

    def run(self):
        def to_list(text):
            try:
                text = json.loads(text)  # 把字符串解析成 Python 列表
            except Exception as e:
                text = [text]  # 如果解析失败，就退化成单句
            return text

        reply, history = qwen3_lora(self.history, self.user_input, self.role)  # 对话
        reply = ollama_qwen3_sentence(reply)  # 句子分割
        history[-1]["content"] = reply
        portrait_list, portrait_history = ollama_qwen3_portrait(reply, self.portrait_history, portrait_type)  # 立绘
        emotion_list = ollama_qwen3_emotion(history)  # 情感
        translate = ollama_qwen3_translate(reply)  # 翻译

        translate = to_list(translate)
        reply = to_list(reply)
        emotion_list = to_list(emotion_list)
        portrait_list = to_list(portrait_list)

        voices = []
        for text, emotion in zip(translate, emotion_list):
            voices.append(gpt_sovits_tts(text, emotion))
        self.finished.emit(reply, portrait_list, history, portrait_history, voices)  # 发回主线程
'''

'''
class qwen3_lora_deepseekAPI_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list)

    def __init__(self, history, portrait_history, user_input, role="user"):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role

    def run(self):
        def to_list(text):
            try:
                return json.loads(text)
            except:
                return [text]

        # 1. 先获取对话回复（这个必须串行，因为依赖前面的历史）
        reply, history = qwen3_lora(self.history, self.user_input, self.role)
        reply = deepseek_sentence(reply) #句子分割
        history[-1]["content"] = reply
        # 2. 使用线程池并发执行所有 DeepSeek 任务
        with ThreadPoolExecutor(max_workers=3) as executor:
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

        voices = []
        for text, emotion in zip(translate_list, emotion_list):
            voices.append(gpt_sovits_tts(text, emotion))
        self.finished.emit(reply_list, portrait_list, history, portrait_history, voices)
'''


class qwen3_lora_Worker(QThread):
    '''将历史与用户信息交给对话模型，然后将回复交给句子分割模型'''
    finished = pyqtSignal(list, list, list, list, list)  # 返回 (AI回复, history)

    def __init__(self, history, portrait_history, user_input, role="user"):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role

    def run(self):
        def to_list(text):
            try:
                text = json.loads(text)  # 把字符串解析成 Python 列表
            except Exception as e:
                text = [text]  # 如果解析失败，就退化成单句
            return text

        reply, history = qwen3_lora(self.history, self.user_input, self.role)  # 对话
        reply = ollama_qwen3_sentence(reply)  # 句子分割
        history[-1]["content"] = reply
        portrait_list, portrait_history = ollama_qwen3_portrait(reply, self.portrait_history, portrait_type)  # 立绘
        emotion_list = ollama_qwen3_emotion(history)  # 情感
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
                future = executor.submit(gpt_sovits_tts, text, emotion)
                tts_futures.append(future)

            # 按顺序获取结果，保持原顺序
            for future in tts_futures:
                voices.append(future.result())

        self.finished.emit(reply, portrait_list, history, portrait_history, voices)  # 发回主线程

class qwen3_lora_deepseekAPI_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list)

    def __init__(self, history, portrait_history, user_input, role="user"):
        super().__init__()
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role

    def run(self):
        def to_list(text):
            try:
                return json.loads(text)
            except:
                return [text]

        # 1. 先获取对话回复（这个必须串行，因为依赖前面的历史）
        reply, history = deepseek_talk(self.history, self.user_input, self.role)
        '''
        reply = deepseek_sentence(reply)  # 句子分割
        history[-1]["content"] = reply
        '''
        # 2. 使用线程池并发执行所有 DeepSeek 任务和 TTS 任务
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
                future = tts_executor.submit(gpt_sovits_tts, text, emotion)
                tts_futures.append(future)

            # 按顺序获取结果，保持原顺序
            for future in tts_futures:
                voices.append(future.result())

        self.finished.emit(reply_list, portrait_list, history, portrait_history, voices)
