from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

from classes.download_manager import DownloadSnapshot, whisper_job_id
from classes.murasame_class import Murasame
from tool.backends import ScreenAnalysis
from tool.config import AppSettings
from tool.tts_assets import TTSAssetState
from tool.whisper_models import model_repository
from ui.settings_dialog import SettingsDialog


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_dialog_and_pet_construct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("AIPET_DATA_DIR")
            previous_model = os.environ.get("AIPET_MODEL_DIR")
            os.environ["AIPET_DATA_DIR"] = directory
            os.environ["AIPET_MODEL_DIR"] = str(
                Path(directory) / "models"
            )
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
                self.assertEqual(
                    [
                        dialog.tabs.tabText(index)
                        for index in range(dialog.tabs.count())
                    ],
                    ["语言模型", "拓展功能", "角色", "自动行为", "显示"],
                )
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
                (Path(directory) / "model.bin").write_bytes(b"model")
                (Path(directory) / "config.json").write_text(
                    "{}",
                    encoding="utf-8",
                )
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

                extraction = DownloadSnapshot(
                    status="extracting",
                    received=25,
                    total=100,
                    current_file="runtime/python.exe",
                )
                dialog._on_download_changed("tts:murasame", extraction)
                self.assertFalse(dialog.tts_extract_progress.isHidden())
                self.assertTrue(dialog.tts_progress.isHidden())
                self.assertEqual(
                    dialog.tts_extract_progress.value(),
                    250,
                )
                installing = DownloadSnapshot(
                    status="installing",
                    received=2,
                    total=3,
                    current_file="activating GPT-SoVITS",
                )
                dialog._on_download_changed("tts:murasame", installing)
                self.assertFalse(dialog.tts_extract_progress.isHidden())
                self.assertEqual(
                    dialog.tts_extract_progress.value(),
                    666,
                )

                dialog.tts_enabled.blockSignals(True)
                dialog.tts_enabled.setChecked(True)
                dialog.tts_enabled.blockSignals(False)
                missing_engine = TTSAssetState(
                    engine_root=None,
                    engine_ready=False,
                    gpt_weight=Path("murasame-gpt.ckpt"),
                    sovits_weight=Path("murasame-sovits.pth"),
                    reference_root=Path("reference_voices"),
                    reference_voices_ready=True,
                )
                with patch(
                    "ui.settings_dialog.QMessageBox.question",
                    return_value=QMessageBox.No,
                ):
                    dialog._on_tts_checked(missing_engine, False)
                self.assertTrue(dialog._tts_engine_download_needed)
                self.assertTrue(dialog.tts_download_button.isEnabled())
                managed_engine = Path(directory) / "managed-engine"
                managed_engine.mkdir()
                (managed_engine / "api_v2.py").write_text(
                    "",
                    encoding="utf-8",
                )
                ready_engine = TTSAssetState(
                    engine_root=managed_engine,
                    engine_ready=True,
                    gpt_weight=Path("murasame-gpt.ckpt"),
                    sovits_weight=Path("murasame-sovits.pth"),
                    reference_root=Path("reference_voices"),
                    reference_voices_ready=True,
                )
                dialog.tts_engine_root.setText(
                    str(Path(directory) / "missing-engine")
                )
                dialog._on_tts_checked(ready_engine, True)
                self.assertEqual(
                    dialog.tts_engine_root.text(),
                    str(managed_engine),
                )
                self.assertEqual(
                    dialog.tts_service_button.text(),
                    "TTS 服务在线",
                )
                self.assertFalse(dialog.tts_service_button.isEnabled())

                dialog._on_tts_checked(ready_engine, False)
                self.assertEqual(
                    dialog.tts_service_button.text(),
                    "启动 TTS 服务",
                )
                self.assertTrue(dialog.tts_service_button.isEnabled())

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

                with patch.object(pet, "start_thread") as start_thread:
                    pet._reset_screen_observation()
                    pet._on_screen_analysis(
                        ScreenAnalysis(
                            software="Visual Studio Code",
                            activity="编辑 Python 项目",
                            topic="AIpet",
                        )
                    )
                    start_thread.assert_not_called()

                    pet._on_screen_analysis(
                        ScreenAnalysis(
                            software="Visual Studio Code",
                            activity="继续编辑 Python 项目",
                            topic="AIpet",
                            significant_change=False,
                        )
                    )
                    start_thread.assert_not_called()

                    changed = ScreenAnalysis(
                        software="浏览器",
                        activity="查看文档",
                        topic="Python API",
                        significant_change=True,
                        change_type="app_switch",
                        change_summary="从编辑器切换到浏览器",
                    )
                    pet._on_screen_analysis(changed)
                    start_thread.assert_called_once()
                    self.assertEqual(
                        start_thread.call_args.kwargs["role"],
                        "system",
                    )

                    pet._on_screen_analysis(
                        ScreenAnalysis(
                            software="终端",
                            activity="查看任务结果",
                            significant_change=True,
                            change_type="completion",
                            change_summary="任务执行完成",
                        )
                    )
                    start_thread.assert_called_once()

                    pet._screen_reply_cooldown_until = 0
                    pet._on_screen_analysis(changed)
                    start_thread.assert_called_once()

                    pet._screen_reply_cooldown_until = 0
                    pet._on_screen_analysis(
                        ScreenAnalysis(
                            software="密码管理器",
                            activity="查看登录信息",
                            significant_change=True,
                            change_type="app_switch",
                            change_summary="切换到密码管理器",
                            sensitive=True,
                        )
                    )
                    start_thread.assert_called_once()
                pet.shutdown()
                dialog.close()
            finally:
                if previous is None:
                    os.environ.pop("AIPET_DATA_DIR", None)
                else:
                    os.environ["AIPET_DATA_DIR"] = previous
                if previous_model is None:
                    os.environ.pop("AIPET_MODEL_DIR", None)
                else:
                    os.environ["AIPET_MODEL_DIR"] = previous_model

    def test_portrait_height_tracks_available_screen_height(self) -> None:
        self.assertEqual(
            Murasame._target_portrait_height(2_000, 1_080, 0.8),
            864,
        )
        self.assertEqual(
            Murasame._target_portrait_height(2_000, 2_160, 0.8),
            1_728,
        )
        self.assertEqual(
            Murasame._target_portrait_height(1_000, 2_160, 0.8),
            1_728,
        )

    def test_screen_pixel_gate_ignores_tiny_changes(self) -> None:
        baseline = np.zeros((54, 96), dtype=np.uint8)
        unchanged = baseline.copy()
        tiny_change = baseline.copy()
        tiny_change[0, 0] = 255
        obvious_change = np.full((54, 96), 255, dtype=np.uint8)

        self.assertFalse(Murasame._pixels_changed(baseline, unchanged))
        self.assertFalse(Murasame._pixels_changed(baseline, tiny_change))
        self.assertTrue(Murasame._pixels_changed(baseline, obvious_change))


if __name__ == "__main__":
    unittest.main()
