"""Platform-neutral hold-to-talk recording and transcription."""

from __future__ import annotations

import threading
import wave
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

import numpy as np
import sounddevice as sd

from aipet.core.audio_devices import (
    audio_backend_access,
    resolve_audio_input_device,
    set_audio_capture_active,
)
from aipet.core.config import get_cache_dir
from aipet.core.runtime_logging import get_logger
from aipet.core.stt import transcribe_full


logger = get_logger("voice")


class AudioRecorder:
    def __init__(
        self,
        samplerate: int = 16000,
        channels: int = 1,
        input_device: str = "",
    ):
        self.samplerate = samplerate
        self.channels = channels
        self.input_device = input_device
        self._stream: Optional[sd.InputStream] = None
        self._stream_active = False
        self._frames = []
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        del frames, time_info
        if status:
            logger.warning("录音设备状态：%s", status)
        with self._lock:
            self._frames.append(indata.copy())

    def start(self) -> None:
        with self._lock:
            self._frames = []
        with audio_backend_access():
            device_index = resolve_audio_input_device(self.input_device)
            selected = sd.query_devices(device_index, kind="input")
            stream = sd.InputStream(
                device=device_index,
                samplerate=self.samplerate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
            )
            try:
                stream.start()
            except Exception:
                stream.close()
                raise
            self._stream = stream
            self._stream_active = True
            set_audio_capture_active(True)
        logger.info("录音开始 | 输入设备=%s", selected["name"])

    def stop_and_save(self, wav_path: str) -> Optional[str]:
        if self._stream is None:
            return None
        self.close()
        with self._lock:
            if not self._frames:
                logger.warning("没有录到有效音频")
                return None
            data = np.concatenate(self._frames, axis=0)
        try:
            Path(wav_path).parent.mkdir(parents=True, exist_ok=True)
            with wave.open(wav_path, "wb") as output:
                output.setnchannels(self.channels)
                output.setsampwidth(2)
                output.setframerate(self.samplerate)
                output.writeframes(data.tobytes())
            logger.info("录音已保存到临时文件")
            return wav_path
        except Exception:
            logger.exception("保存 WAV 失败")
            return None

    def close(self) -> None:
        stream = self._stream
        if stream is None:
            return
        with audio_backend_access():
            try:
                try:
                    stream.stop()
                finally:
                    stream.close()
            finally:
                self._stream = None
                if self._stream_active:
                    self._stream_active = False
                    set_audio_capture_active(False)


class HoldToTalkSession:
    def __init__(
        self,
        on_text_ready: Callable[[str], None],
        hold_seconds: float = 2.0,
        on_record_start: Optional[Callable[[], None]] = None,
        on_record_end: Optional[Callable[[], None]] = None,
        model_name: str = "large-v3",
        model_directory: str = "",
        device: str = "auto",
        input_device: str = "",
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.on_text_ready = on_text_ready
        self.hold_seconds = hold_seconds
        self.on_record_start = on_record_start
        self.on_record_end = on_record_end
        self.model_name = model_name
        self.model_directory = model_directory
        self.device = device
        self.input_device = input_device
        self.on_error = on_error
        self._pressed = False
        self._recording = False
        self._recognizing = False
        self._hold_timer: Optional[threading.Timer] = None
        self._recorder = AudioRecorder(input_device=input_device)

    def press(self) -> None:
        if self._recognizing or self._pressed:
            return
        self._pressed = True
        self._hold_timer = threading.Timer(
            self.hold_seconds,
            self._maybe_start_record,
        )
        self._hold_timer.daemon = True
        self._hold_timer.start()

    def release(self) -> None:
        self._pressed = False
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None
        if self._recording:
            self._recording = False
            self._handle_record_done()

    def stop_session(self) -> None:
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None
        self._pressed = False
        self._recording = False
        self._recognizing = False
        self._recorder.close()

    def _maybe_start_record(self) -> None:
        if not self._pressed:
            return
        self._recording = True
        try:
            self._recorder.start()
            if self.on_record_start:
                try:
                    self.on_record_start()
                except Exception:
                    logger.exception("录音开始回调失败")
        except Exception as exc:
            self._recording = False
            logger.exception("启动录音失败")
            if self.on_error:
                self.on_error(str(exc))

    def _handle_record_done(self) -> None:
        self._recognizing = True
        wav_path = str(
            get_cache_dir() / "recordings" / f"{uuid4().hex}.wav"
        )
        saved = self._recorder.stop_and_save(wav_path)
        if self.on_record_end:
            try:
                self.on_record_end()
            except Exception:
                logger.exception("录音结束回调失败")
        if not saved:
            self._recognizing = False
            if self.on_error:
                self.on_error("没有录到有效音频，请检查麦克风后重试。")
            return

        def transcribe() -> None:
            try:
                text = (
                    transcribe_full(
                        saved,
                        model_size=self.model_name,
                        model_directory=self.model_directory,
                        device=self.device,
                    )
                    or ""
                ).strip()
                if not text:
                    logger.warning("语音识别结果为空")
                    if self.on_error:
                        self.on_error("没有识别到有效语音，请重试。")
                    return
                logger.info("语音识别完成（内容不写入日志）")
                try:
                    self.on_text_ready(text)
                except Exception:
                    logger.exception("语音识别回调处理失败")
            except Exception as exc:
                logger.exception("语音识别失败")
                if self.on_error:
                    self.on_error(str(exc))
            finally:
                self._recognizing = False
                try:
                    Path(saved).unlink(missing_ok=True)
                    logger.info("语音临时文件已删除")
                except Exception as exc:
                    logger.warning("删除语音临时文件失败：%s", exc)

        thread = threading.Thread(target=transcribe, daemon=True)
        try:
            thread.start()
        except Exception as exc:
            self._recognizing = False
            Path(saved).unlink(missing_ok=True)
            logger.exception("启动语音识别线程失败")
            if self.on_error:
                self.on_error(str(exc))


__all__ = ["AudioRecorder", "HoldToTalkSession"]
