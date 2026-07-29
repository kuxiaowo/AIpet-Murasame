"""Windows Caps Lock voice-input trigger."""

from __future__ import annotations

from typing import Optional

from pynput import keyboard

from aipet.core.runtime_logging import get_logger
from aipet.core.voice_input import HoldToTalkSession


logger = get_logger("voice")


class CapslockVoiceTrigger(HoldToTalkSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._listener: Optional[keyboard.Listener] = None

    def start(self) -> None:
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
        self.stop_session()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        if key == keyboard.Key.caps_lock:
            self.press()

    def _on_release(self, key) -> None:
        if key == keyboard.Key.caps_lock:
            self.release()


__all__ = ["CapslockVoiceTrigger"]
