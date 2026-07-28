"""macOS Option+V voice-input trigger."""

from __future__ import annotations

from typing import Optional

from pynput import keyboard

from aipet.core.runtime_logging import get_logger
from aipet.core.voice_input import HoldToTalkSession


logger = get_logger("voice")
_OPTION_KEYS = {
    keyboard.Key.alt,
    keyboard.Key.alt_l,
    keyboard.Key.alt_r,
}


class OptionVVoiceTrigger(HoldToTalkSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._option_pressed = False
        self._v_pressed = False
        self._listener: Optional[keyboard.Listener] = None

    @staticmethod
    def _is_v(key) -> bool:
        return (
            (getattr(key, "char", "") or "").casefold() == "v"
            or getattr(key, "vk", None) == 9
        )

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            daemon=True,
        )
        self._listener.start()
        logger.info("Option+V 语音触发已启动")

    def stop(self) -> None:
        self.stop_session()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        if key in _OPTION_KEYS:
            self._option_pressed = True
        elif self._is_v(key):
            self._v_pressed = True
        if self._option_pressed and self._v_pressed:
            self.press()

    def _on_release(self, key) -> None:
        was_pressed = self._option_pressed and self._v_pressed
        if key in _OPTION_KEYS:
            self._option_pressed = False
        elif self._is_v(key):
            self._v_pressed = False
        if was_pressed:
            self.release()


__all__ = ["OptionVVoiceTrigger"]
