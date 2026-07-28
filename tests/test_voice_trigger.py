from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from tool.voice_trigger import CapslockVoiceTrigger
except (ImportError, OSError):
    CapslockVoiceTrigger = None


@unittest.skipIf(
    CapslockVoiceTrigger is None,
    "optional voice dependencies are unavailable",
)
class VoiceTriggerTests(unittest.TestCase):
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
                    "tool.voice_trigger.get_cache_dir",
                    return_value=Path(directory),
                ),
                patch(
                    "tool.voice_trigger.transcribe_full",
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


if __name__ == "__main__":
    unittest.main()
