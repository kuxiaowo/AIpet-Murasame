from __future__ import annotations

import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from classes.download_manager import DownloadSnapshot, whisper_job_id
from classes.murasame_class import Murasame
from tool.config import AppSettings
from tool.whisper_models import model_repository
from ui.settings_dialog import SettingsDialog


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_dialog_and_pet_construct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("AIPET_DATA_DIR")
            os.environ["AIPET_DATA_DIR"] = directory
            try:
                settings = AppSettings()
                dialog = SettingsDialog(settings)
                pet = Murasame(settings)
                self.assertGreater(pet.width(), 0)
                self.assertGreater(pet.height(), 0)
                self.assertEqual(
                    dialog._form_settings().mode,
                    "ollama",
                )
                dialog._set_combo_data(dialog.language_combo, "zh-CN")
                self.assertEqual(dialog.windowTitle(), "AIpet 设置")
                self.assertEqual(dialog.tabs.tabText(0), "模型")
                self.assertEqual(
                    dialog._form_settings().ui_language,
                    "zh-CN",
                )
                self.assertGreaterEqual(
                    dialog.stt_model.findText("large-v3"),
                    0,
                )
                self.assertIn(
                    "启用语音输入",
                    dialog.whisper_status.text(),
                )
                progress = DownloadSnapshot(
                    status="downloading",
                    received=50,
                    total=100,
                    current_file="model.bin",
                )
                dialog._on_download_changed(
                    whisper_job_id(model_repository("large-v3")),
                    progress,
                )
                self.assertFalse(dialog.whisper_progress.isHidden())
                self.assertEqual(dialog.whisper_progress.value(), 500)
                dialog.stt_model.setCurrentText(directory)
                dialog.stt_enabled.setChecked(True)
                deadline = time.monotonic() + 2
                while (
                    dialog._whisper_check_worker is not None
                    and time.monotonic() < deadline
                ):
                    self.app.processEvents()
                self.assertIn("本地已安装", dialog.whisper_status.text())
                self.assertFalse(dialog.whisper_download_button.isEnabled())

                dialog.ollama_chat_model.setCurrentText("custom-chat")
                dialog._model_target = ("ollama", "deepseek")
                dialog._on_models_ready(["model-a", "model-b"])
                self.assertEqual(
                    dialog.ollama_chat_model.currentText(),
                    "custom-chat",
                )
                self.assertGreaterEqual(
                    dialog.ollama_chat_model.findText("model-a"),
                    0,
                )
                pet._start_thinking_animation()
                self.assertTrue(pet.thinking_timer.isActive())
                self.assertTrue(pet.display_text.endswith("."))
                pet._thinking_step()
                self.assertTrue(pet.display_text.endswith(".."))
                pet._stop_thinking_animation()
                self.assertFalse(pet.thinking_timer.isActive())
                pet.shutdown()
                dialog.close()
            finally:
                if previous is None:
                    os.environ.pop("AIPET_DATA_DIR", None)
                else:
                    os.environ["AIPET_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
