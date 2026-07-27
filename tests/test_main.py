from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import main
from tool.config import AppSettings, STTSettings


class MainTests(unittest.TestCase):
    def test_macos_uses_native_hotkey_voice_trigger(self) -> None:
        settings = AppSettings(stt=STTSettings(enabled=True))
        fake_trigger = Mock()
        fake_trigger.return_value.start.return_value = None
        fake_bridge = Mock()
        with patch.object(main.sys, "platform", "darwin"):
            with patch("main.VoiceBridge", return_value=fake_bridge):
                with patch("tool.voice_trigger.MacOSHotkeyVoiceTrigger", fake_trigger):
                    trigger = main.configure_voice_trigger(Mock(), settings, Mock())
        self.assertIs(trigger, fake_trigger.return_value)
        fake_trigger.assert_called_once()


if __name__ == "__main__":
    unittest.main()
