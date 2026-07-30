"""macOS Option+V voice-input trigger."""

from __future__ import annotations

from AppKit import (
    NSEvent,
    NSEventMaskKeyDown,
    NSEventMaskKeyUp,
    NSEventModifierFlagOption,
    NSEventTypeKeyDown,
    NSEventTypeKeyUp,
)
from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)

from aipet.core.runtime_logging import get_logger
from aipet.core.voice_input import HoldToTalkSession


logger = get_logger("voice")
_V_KEY_CODE = 9


class OptionVVoiceTrigger(HoldToTalkSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._monitors: list[object] = []

    def start(self) -> None:
        if self._monitors:
            return
        if not self._has_accessibility_permission():
            raise PermissionError(
                "Option+V requires Accessibility permission. "
                "Allow AIpet-Murasame in System Settings > Privacy & Security "
                "> Accessibility, then try again."
            )
        mask = NSEventMaskKeyDown | NSEventMaskKeyUp
        global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask,
            self._handle_global_event,
        )
        local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            mask,
            self._handle_local_event,
        )
        self._monitors = [global_monitor, local_monitor]
        logger.info("Option+V 语音触发已启动")

    @staticmethod
    def _has_accessibility_permission() -> bool:
        return bool(
            AXIsProcessTrustedWithOptions(
                {kAXTrustedCheckOptionPrompt: True}
            )
        )

    def stop(self) -> None:
        self.stop_session()
        for monitor in self._monitors:
            NSEvent.removeMonitor_(monitor)
        self._monitors = []

    def _handle_global_event(self, event) -> None:
        self._handle_event(event)

    def _handle_local_event(self, event):
        self._handle_event(event)
        return event

    def _handle_event(self, event) -> None:
        if event.keyCode() != _V_KEY_CODE:
            return
        if (
            event.type() == NSEventTypeKeyDown
            and event.modifierFlags() & NSEventModifierFlagOption
        ):
            self.press()
        elif event.type() == NSEventTypeKeyUp:
            self.release()


__all__ = ["OptionVVoiceTrigger"]
