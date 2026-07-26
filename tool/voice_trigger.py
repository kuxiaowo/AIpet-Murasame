import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import numpy as np
import sounddevice as sd
from pynput import keyboard

from tool.config import get_cache_dir
from tool.runtime_logging import get_logger
from tool.stt import transcribe_full


logger = get_logger("voice")


class AudioRecorder:
    """简单的麦克风录音器，录制到内存后写入 WAV 文件。"""

    def __init__(self, samplerate: int = 16000, channels: int = 1):
        self.samplerate = samplerate
        self.channels = channels
        self._stream: Optional[sd.InputStream] = None
        self._frames = []
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning("录音设备状态：%s", status)
        with self._lock:
            self._frames.append(indata.copy())

    def start(self) -> None:
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        logger.info("录音开始")

    def stop_and_save(self, wav_path: str) -> Optional[str]:
        if self._stream is None:
            return None
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            if not self._frames:
                logger.warning("没有录到有效音频")
                return None
            data = np.concatenate(self._frames, axis=0)
        try:
            Path(wav_path).parent.mkdir(parents=True, exist_ok=True)
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # int16
                wf.setframerate(self.samplerate)
                wf.writeframes(data.tobytes())
            logger.info("录音已保存到临时文件")
            return wav_path
        except Exception as exc:
            logger.exception("保存 WAV 失败")
            return None


class CapslockVoiceTrigger:
    """
    全局监听 CapsLock:
    - 按下超过 hold_seconds 秒开始录音
    - 松开停止录音，写入 tmp/*.wav
    - 调用 STT 转写后，通过回调把文本交给对话逻辑
    """

    def __init__(
        self,
        on_text_ready: Callable[[str], None],
        hold_seconds: float = 2.0,
        on_record_start: Optional[Callable[[], None]] = None,
        on_record_end: Optional[Callable[[], None]] = None,
        model_name: str = "large-v3",
        device: str = "auto",
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.on_text_ready = on_text_ready
        self.hold_seconds = hold_seconds
        self.on_record_start = on_record_start
        self.on_record_end = on_record_end
        self.model_name = model_name
        self.device = device
        self.on_error = on_error

        self._caps_pressed = False
        self._press_time: Optional[float] = None
        self._recording = False
        self._hold_timer: Optional[threading.Timer] = None

        self._recorder = AudioRecorder()
        self._listener: Optional[keyboard.Listener] = None

    def start(self) -> None:
        """在单独线程启动全局键盘监听。"""
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            daemon=True,
        )
        self._listener.start()
        logger.info("CapsLock 语音触发已启动")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    # 键盘事件处理
    def _on_press(self, key) -> None:
        try:
            if key != keyboard.Key.caps_lock:
                return
        except Exception:
            return
        if self._caps_pressed:
            return
        self._caps_pressed = True
        self._press_time = time.time()
        # 启动一个延时任务，超过 hold_seconds 后开始录音
        self._hold_timer = threading.Timer(self.hold_seconds, self._maybe_start_record)
        self._hold_timer.daemon = True
        self._hold_timer.start()

    def _on_release(self, key) -> None:
        try:
            if key != keyboard.Key.caps_lock:
                return
        except Exception:
            return

        self._caps_pressed = False
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None

        if self._recording:
            # 松开键时结束录音并启动转写
            self._recording = False
            self._handle_record_done()

    def _maybe_start_record(self) -> None:
        if not self._caps_pressed:
            return
        # 按住时间满足阈值，开始录音
        self._recording = True
        try:
            self._recorder.start()
            if self.on_record_start:
                try:
                    self.on_record_start()
                except Exception as exc:
                    logger.exception("录音开始回调失败")
        except Exception as exc:
            self._recording = False
            logger.exception("启动录音失败")

    # 录音结束 -> 保存 WAV -> STT -> 回调
    def _handle_record_done(self) -> None:
        recording_dir = get_cache_dir() / "recordings"
        wav_path = str(recording_dir / f"{uuid4().hex}.wav")

        saved = self._recorder.stop_and_save(wav_path)
        if self.on_record_end:
            try:
                self.on_record_end()
            except Exception as exc:
                logger.exception("录音结束回调失败")
        if not saved:
            return

        def _stt_and_callback():
            try:
                text = transcribe_full(
                    saved,
                    model_size=self.model_name,
                    device=self.device,
                )
                text = (text or "").strip()
                if not text:
                    logger.warning("语音识别结果为空")
                    return
                logger.info("语音识别完成（内容不写入日志）")
                try:
                    self.on_text_ready(text)
                except Exception as exc:
                    logger.exception("语音识别回调处理失败")
            except Exception as exc:
                logger.exception("语音识别失败")
                if self.on_error:
                    self.on_error(str(exc))
            finally:
                try:
                    Path(saved).unlink(missing_ok=True)
                    logger.info("语音临时文件已删除")
                except Exception as exc:
                    logger.warning("删除语音临时文件失败：%s", exc)

        t = threading.Thread(target=_stt_and_callback, daemon=True)
        t.start()


__all__ = ["CapslockVoiceTrigger"]
