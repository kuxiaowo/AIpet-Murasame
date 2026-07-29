from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from pynput import keyboard
except (ImportError, OSError):
    keyboard = None

try:
    from aipet.platforms.windows.voice_trigger import CapslockVoiceTrigger
except (ImportError, OSError):
    CapslockVoiceTrigger = None

try:
    from aipet.platforms.macos.voice_trigger import OptionVVoiceTrigger
except (ImportError, OSError):
    OptionVVoiceTrigger = None


@unittest.skipIf(
    CapslockVoiceTrigger is None or keyboard is None,
    "Windows voice dependencies are unavailable",
)
class WindowsVoiceTriggerTests(unittest.TestCase):
    def test_windows_caps_lock_controls_hold_session(self) -> None:
        trigger = CapslockVoiceTrigger(on_text_ready=Mock())
        trigger.press = Mock()
        trigger.release = Mock()

        trigger._on_press(keyboard.Key.caps_lock)
        trigger.press.assert_called_once_with()
        trigger._on_release(keyboard.Key.caps_lock)
        trigger.release.assert_called_once_with()

    def test_windows_ignores_keys_that_cannot_be_compared(self) -> None:
        class UncomparableKey:
            def __eq__(self, other) -> bool:
                del other
                raise RuntimeError("comparison failed")

        trigger = CapslockVoiceTrigger(on_text_ready=Mock())
        trigger.press = Mock()
        trigger.release = Mock()

        trigger._on_press(UncomparableKey())
        trigger._on_release(UncomparableKey())

        trigger.press.assert_not_called()
        trigger.release.assert_not_called()

    def test_repeated_caps_lock_press_schedules_one_hold_timer(self) -> None:
        trigger = CapslockVoiceTrigger(on_text_ready=Mock())

        with patch("aipet.core.voice_input.threading.Timer") as timer:
            trigger._on_press(keyboard.Key.caps_lock)
            trigger._on_press(keyboard.Key.caps_lock)

        timer.assert_called_once()

    def test_short_caps_lock_press_cancels_hold_timer(self) -> None:
        trigger = CapslockVoiceTrigger(on_text_ready=Mock())

        with patch("aipet.core.voice_input.threading.Timer") as timer:
            trigger._on_press(keyboard.Key.caps_lock)
            trigger._on_release(keyboard.Key.caps_lock)

        timer.return_value.cancel.assert_called_once_with()
        self.assertFalse(trigger._pressed)
        self.assertFalse(trigger._recording)

    def test_recognizing_ignores_new_caps_lock_press(self) -> None:
        trigger = CapslockVoiceTrigger(on_text_ready=Mock())
        trigger._recognizing = True

        with patch("aipet.core.voice_input.threading.Timer") as timer:
            trigger._on_press(keyboard.Key.caps_lock)

        timer.assert_not_called()
        self.assertFalse(trigger._pressed)

    def test_windows_listener_start_and_stop_are_idempotent(self) -> None:
        trigger = CapslockVoiceTrigger(on_text_ready=Mock())
        trigger._recorder.close = Mock()

        with patch(
            "aipet.platforms.windows.voice_trigger.keyboard.Listener"
        ) as listener:
            trigger.start()
            trigger.start()
            trigger.stop()

        listener.assert_called_once()
        listener.return_value.start.assert_called_once_with()
        listener.return_value.stop.assert_called_once_with()
        trigger._recorder.close.assert_called_once_with()
        self.assertIsNone(trigger._listener)

    def test_missing_audio_reports_error_and_clears_recognizing_state(
        self,
    ) -> None:
        errors: list[str] = []
        record_end = Mock()
        trigger = CapslockVoiceTrigger(
            on_text_ready=Mock(),
            on_record_end=record_end,
            on_error=errors.append,
        )
        trigger._recorder.stop_and_save = Mock(return_value=None)

        trigger._handle_record_done()

        record_end.assert_called_once_with()
        self.assertFalse(trigger._recognizing)
        self.assertEqual(len(errors), 1)
        self.assertIn("没有录到有效音频", errors[0])

    def test_empty_transcript_reports_error_and_finishes_recognition(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "recording.wav"
            audio_path.write_bytes(b"audio")
            errors: list[str] = []
            completed = threading.Event()

            def on_error(message: str) -> None:
                errors.append(message)
                completed.set()

            trigger = CapslockVoiceTrigger(
                on_text_ready=Mock(),
                on_error=on_error,
            )
            trigger._recorder.stop_and_save = Mock(
                return_value=str(audio_path)
            )

            with (
                patch(
                    "aipet.core.voice_input.get_cache_dir",
                    return_value=Path(directory),
                ),
                patch(
                    "aipet.core.voice_input.transcribe_full",
                    return_value="",
                ),
            ):
                trigger._handle_record_done()
                self.assertTrue(completed.wait(timeout=2))

            self.assertFalse(trigger._recognizing)
            self.assertEqual(len(errors), 1)
            self.assertIn("没有识别到有效语音", errors[0])
            deadline = time.monotonic() + 2
            while audio_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(audio_path.exists())

    def test_transcript_is_delivered_and_temporary_audio_is_deleted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "recording.wav"
            audio_path.write_bytes(b"audio")
            completed = threading.Event()
            texts: list[str] = []

            def on_text_ready(text: str) -> None:
                texts.append(text)
                completed.set()

            trigger = CapslockVoiceTrigger(on_text_ready=on_text_ready)
            trigger._recorder.stop_and_save = Mock(
                return_value=str(audio_path)
            )

            with (
                patch(
                    "aipet.core.voice_input.get_cache_dir",
                    return_value=Path(directory),
                ),
                patch(
                    "aipet.core.voice_input.transcribe_full",
                    return_value="  测试语音  ",
                ),
            ):
                trigger._handle_record_done()
                self.assertTrue(completed.wait(timeout=2))

            deadline = time.monotonic() + 2
            while audio_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(texts, ["测试语音"])
            self.assertFalse(trigger._recognizing)
            self.assertFalse(audio_path.exists())


@unittest.skipIf(
    OptionVVoiceTrigger is None,
    "macOS voice dependencies are unavailable",
)
class MacOSVoiceTriggerTests(unittest.TestCase):
    def test_macos_option_v_controls_hold_session(self) -> None:
        trigger = OptionVVoiceTrigger(on_text_ready=Mock())
        trigger.press = Mock()
        trigger.release = Mock()
        option_v_down = Mock()
        option_v_down.keyCode.return_value = 9
        option_v_down.type.return_value = 10
        option_v_down.modifierFlags.return_value = 524288
        v_up = Mock()
        v_up.keyCode.return_value = 9
        v_up.type.return_value = 11

        trigger._handle_event(option_v_down)
        trigger.press.assert_called_once_with()
        trigger._handle_event(v_up)
        trigger.release.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
