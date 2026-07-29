from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from aipet.core.download_manager import DownloadSnapshot, whisper_job_id
from aipet.ui.pet import Murasame
from aipet.core.workers import ConversationResult
from main import move_pet_to_configured_screen
from aipet.core.audio_devices import AudioInputDevice
from aipet.core.backends import ScreenAnalysis, parse_character_reply
from aipet.core.cache import CacheClearResult
from aipet.core.config import AppSettings
from aipet.core.portraits import layers_for
from aipet.core.tts_assets import TTSAssetState
from aipet.core.whisper_models import model_repository
from aipet.ui.settings_dialog import SettingsDialog


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_status_text_can_use_the_user_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"AIPET_DATA_DIR": directory},
            ):
                settings = AppSettings()
                settings.character.user_name = "主人"
                pet = Murasame(settings)
                try:
                    pet.show_text(
                        "正在录音……",
                        typing=False,
                        speaker_name=settings.character.user_name,
                    )
                    self.assertTrue(pet.display_text.startswith("【主人】\n"))

                    pet.show_text("角色台词", typing=False)
                    self.assertTrue(pet.display_text.startswith("【丛雨】\n"))
                finally:
                    pet.shutdown()

    def test_tts_bootstrap_failure_keeps_its_error_visible(self) -> None:
        dialog = SettingsDialog(AppSettings())
        try:
            dialog._on_tts_bootstrap_failed("network failed")
            dialog._finish_tts_bootstrap_worker(MagicMock())
            self.assertEqual(dialog._tts_status_key, "tts_bootstrap_failed")
        finally:
            dialog.close()

    def test_topmost_watchdog_tracks_window_visibility(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AIPET_DATA_DIR": directory}),
            patch(
                "aipet.ui.pet.native_topmost_available",
                return_value=True,
            ),
            patch(
                "aipet.ui.pet.ensure_window_topmost",
                return_value=True,
            ) as ensure_topmost,
        ):
            pet = Murasame(AppSettings())
            try:
                pet.show()
                self.app.processEvents()
                self.assertTrue(pet._topmost_timer.isActive())
                ensure_topmost.assert_called()

                pet.hide()
                self.app.processEvents()
                self.assertFalse(pet._topmost_timer.isActive())
            finally:
                pet.shutdown()

    def test_recording_device_selection_round_trips(self) -> None:
        selected = AudioInputDevice(
            index=37,
            name="Test Microphone",
            hostapi="Windows WASAPI",
            max_input_channels=1,
        )
        newly_connected = AudioInputDevice(
            index=41,
            name="New USB Microphone",
            hostapi="Windows WASAPI",
            max_input_channels=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings()
            settings.stt.input_device = selected.identifier
            settings.stt.device = "cuda"
            settings.ui_language = "zh-CN"
            with (
                patch.dict(
                    os.environ,
                    {"AIPET_DATA_DIR": directory},
                ),
                patch(
                    "aipet.ui.settings_dialog.refresh_audio_input_devices",
                    return_value=(selected, [selected]),
                ),
            ):
                dialog = SettingsDialog(settings)
                try:
                    self.assertEqual(
                        dialog.stt_input_device.currentData(),
                        selected.identifier,
                    )
                    self.assertEqual(
                        dialog._form_settings().stt.input_device,
                        selected.identifier,
                    )
                    self.assertEqual(dialog.stt_device.currentData(), "cuda")
                    self.assertEqual(
                        dialog.stt_device.currentText(),
                        "CUDA（请使用 AIpet-with-cuda 版本，否则无法使用）",
                    )
                    self.assertEqual(
                        dialog._form_settings().stt.device,
                        "cuda",
                    )
                    dialog._set_combo_data(dialog.language_combo, "en")
                    self.assertEqual(
                        dialog.stt_device.currentText(),
                        (
                            "CUDA (requires the AIpet-with-cuda build; "
                            "unavailable otherwise)"
                        ),
                    )
                    with (
                        patch(
                            "aipet.ui.settings_dialog.refresh_audio_input_devices",
                            return_value=(selected, [selected, newly_connected]),
                        ),
                    ):
                        dialog._refresh_audio_input_devices()
                    self.assertEqual(
                        dialog.stt_input_device.currentData(),
                        selected.identifier,
                    )
                    self.assertGreaterEqual(
                        dialog.stt_input_device.findData(
                            newly_connected.identifier
                        ),
                        0,
                    )

                    with patch.object(dialog, "_auto_fetch_models"):
                        dialog.show()
                        self.app.processEvents()
                    self.assertTrue(
                        dialog._audio_device_refresh_timer.isActive()
                    )
                    dialog.hide()
                    self.app.processEvents()
                    self.assertFalse(
                        dialog._audio_device_refresh_timer.isActive()
                    )
                finally:
                    dialog.close()

    def test_disabled_screen_vision_is_inert(self) -> None:
        settings = AppSettings(mode="api")
        settings.vision.enabled = False
        settings.vision.provider = "ollama"
        dialog = SettingsDialog(settings)

        self.assertFalse(dialog.vision_options.isEnabled())
        self.assertFalse(dialog.vision_provider.isEnabled())
        self.assertFalse(dialog.fetch_vision_models_button.isEnabled())
        with patch.object(dialog, "_start_model_fetch") as start_fetch:
            dialog._auto_fetch_models()
            dialog._fetch_vision_models()
            start_fetch.assert_not_called()

        dialog.vision_enabled.setChecked(True)
        self.assertTrue(dialog.vision_options.isEnabled())
        self.assertTrue(dialog.vision_provider.isEnabled())
        self.assertTrue(dialog.fetch_vision_models_button.isEnabled())
        with patch.object(dialog, "_start_model_fetch") as start_fetch:
            dialog._auto_fetch_models()
            start_fetch.assert_called_once_with(
                vision=True,
                notify_if_busy=False,
            )

    def test_disabled_tts_greys_out_all_options(self) -> None:
        settings = AppSettings()
        settings.tts.enabled = False
        dialog = SettingsDialog(settings)
        try:
            self.assertTrue(dialog.tts_enabled.isEnabled())
            for field in (
                dialog.tts_backend,
                dialog.tts_url,
                dialog.tts_timeout,
                dialog.tts_engine_root,
                dialog.tts_engine_browse,
                dialog.tts_model_dir,
                dialog.tts_model_browse,
                dialog.tts_autodl_ssh_command,
                dialog.tts_autodl_password,
                dialog.tts_autodl_remote_command,
                dialog.tts_autodl_reference_root,
                dialog.tts_service_button,
                dialog.tts_download_button,
            ):
                self.assertFalse(field.isEnabled(), field.objectName())

            tts_label_keys = (
                "tts_backend",
                "tts_endpoint",
                "tts_timeout",
                "tts_engine_root",
                "tts_model_dir",
                "tts_autodl_ssh_command",
                "tts_autodl_password",
                "tts_autodl_remote_command",
                "tts_autodl_reference_root",
            )
            for key in tts_label_keys:
                for label in dialog._form_labels[key]:
                    self.assertFalse(label.isEnabled(), key)
        finally:
            dialog.close()

    def test_tts_backend_hides_irrelevant_rows(self) -> None:
        settings = AppSettings()
        settings.tts.enabled = False
        settings.tts.backend = "local"
        dialog = SettingsDialog(settings)
        try:
            local_keys = (
                "tts_endpoint",
                "tts_engine_root",
                "tts_model_dir",
            )
            autodl_keys = (
                "tts_autodl_ssh_command",
                "tts_autodl_password",
                "tts_autodl_remote_command",
                "tts_autodl_reference_root",
            )
            for key in local_keys:
                self.assertFalse(
                    dialog._form_fields[key][0].isHidden(),
                    key,
                )
                self.assertFalse(
                    dialog._form_labels[key][0].isHidden(),
                    key,
                )
            for key in autodl_keys:
                self.assertTrue(
                    dialog._form_fields[key][0].isHidden(),
                    key,
                )
                self.assertTrue(
                    dialog._form_labels[key][0].isHidden(),
                    key,
                )
            self.assertFalse(dialog.tts_download_button.isHidden())

            dialog._set_combo_data(dialog.tts_backend, "autodl")
            for key in local_keys:
                self.assertTrue(
                    dialog._form_fields[key][0].isHidden(),
                    key,
                )
                self.assertTrue(
                    dialog._form_labels[key][0].isHidden(),
                    key,
                )
            for key in autodl_keys:
                self.assertFalse(
                    dialog._form_fields[key][0].isHidden(),
                    key,
                )
                self.assertFalse(
                    dialog._form_labels[key][0].isHidden(),
                    key,
                )
            self.assertTrue(dialog.tts_download_button.isHidden())
        finally:
            dialog.close()

    def test_settings_help_buttons_replace_empty_title_bar_help(
        self,
    ) -> None:
        settings = AppSettings(ui_language="zh-CN")
        with (
            patch(
                "aipet.ui.settings_dialog.refresh_audio_input_devices",
                return_value=(None, []),
            ),
        ):
            dialog = SettingsDialog(settings)
        try:
            self.assertFalse(
                bool(dialog.windowFlags() & Qt.WindowContextHelpButtonHint)
            )
            with patch(
                "aipet.ui.settings_dialog.QMessageBox.information"
            ) as information:
                dialog.automation_help_button.click()
                information.assert_called_once()
                self.assertIn("思考提醒", information.call_args.args[2])

                information.reset_mock()
                dialog.display_help_button.click()
                information.assert_called_once()
                self.assertIn("屏幕编号", information.call_args.args[2])
        finally:
            dialog.close()

    def test_models_tab_does_not_compress_form_rows(self) -> None:
        previous_font = self.app.font()
        try:
            self.app.setFont(QFont("Segoe UI", 18))
            settings = AppSettings(mode="api", ui_language="zh-CN")
            dialog = SettingsDialog(settings)
            dialog.tabs.setCurrentIndex(0)
            dialog.show()
            self.app.processEvents()

            self.assertGreaterEqual(
                dialog.api_group.height(),
                dialog.api_group.minimumSizeHint().height(),
            )
            for field in (
                dialog.deepseek_key,
                dialog.deepseek_url,
                dialog.deepseek_chat_model,
                dialog.api_timeout,
            ):
                self.assertGreaterEqual(
                    field.height(),
                    field.minimumSizeHint().height(),
                )
            dialog.close()
        finally:
            self.app.setFont(previous_font)

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
                screen = self.app.primaryScreen()
                self.assertIsNotNone(screen)
                settings.display.screen_name = screen.name()
                settings.display.window_x = 24
                settings.display.window_y = 36
                settings.character.outfit = "casual"
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
                    [
                        "语言模型",
                        "拓展功能",
                        "角色",
                        "自动行为",
                        "显示",
                        "其他",
                    ],
                )
                self.assertEqual(
                    dialog._form_settings().ui_language,
                    "zh-CN",
                )
                self.assertEqual(
                    dialog._form_settings().character.outfit,
                    "casual",
                )
                default_model_root = Path(
                    os.environ["AIPET_MODEL_DIR"]
                ).resolve()
                self.assertEqual(
                    Path(dialog.tts_engine_root.text()),
                    default_model_root / "tts" / "GPT-SoVITS",
                )
                self.assertEqual(
                    Path(dialog.tts_model_dir.text()),
                    default_model_root / "tts" / "Murasame_SoVITS",
                )
                self.assertEqual(
                    Path(dialog.whisper_model_dir.text()),
                    default_model_root / "whisper" / "large-v3",
                )
                dialog.show_log_console.setChecked(True)
                self.assertTrue(
                    dialog._form_settings().display.show_log_console
                )
                self.assertEqual(
                    dialog._form_settings().display.window_x,
                    24,
                )
                self.assertEqual(
                    dialog._form_settings().display.window_y,
                    36,
                )
                move_pet_to_configured_screen(self.app, pet, settings)
                available = screen.availableGeometry()
                expected_x = min(
                    available.x() + 24,
                    max(
                        available.left(),
                        available.right() - pet.width() + 1,
                    ),
                )
                expected_y = min(
                    available.y() + 36,
                    max(
                        available.top(),
                        available.bottom() - pet.height() + 1,
                    ),
                )
                self.assertEqual(pet.x(), expected_x)
                self.assertEqual(pet.y(), expected_y)
                pet.move(available.x() + 12, available.y() + 18)
                pet.remember_window_position()
                self.assertEqual(pet.settings.display.window_x, 12)
                self.assertEqual(pet.settings.display.window_y, 18)
                self.assertEqual(
                    pet.settings.display.screen_name,
                    screen.name(),
                )
                dialog.whisper_model_dir.clear()
                with patch(
                    "aipet.ui.settings_dialog.QMessageBox.warning"
                ) as warning:
                    self.assertIsNone(
                        dialog._require_download_directory(
                            dialog.whisper_model_dir,
                            "whisper_path_required",
                        )
                    )
                warning.assert_called_once()
                dialog.tts_enabled.blockSignals(True)
                dialog.tts_enabled.setChecked(True)
                dialog.tts_enabled.blockSignals(False)
                dialog.tts_model_dir.clear()
                with (
                    patch(
                        "aipet.ui.settings_dialog.QMessageBox.warning"
                    ) as warning,
                    patch.object(
                        dialog.download_manager,
                        "start_tts",
                    ) as start_tts,
                ):
                    dialog._request_tts_download()
                warning.assert_called_once()
                start_tts.assert_not_called()
                dialog.tts_enabled.setChecked(False)

                dialog.do_not_disturb.setChecked(True)
                self.assertTrue(
                    dialog._form_settings().idle.do_not_disturb
                )
                pet.set_dnd_enabled(True)
                self.assertTrue(pet.is_dnd_enabled())
                self.assertTrue(pet.settings.idle.do_not_disturb)
                pet.set_dnd_enabled(False)
                dialog.do_not_disturb.setChecked(False)

                pet.move(
                    available.center().x() - pet.width() // 2,
                    available.bottom() - pet.height() + 1,
                )
                previous_center_x = pet.geometry().center().x()
                previous_bottom = pet.geometry().bottom()
                pet.update_portrait(
                    layers_for("a", "高兴", "uniform"),
                    "a",
                    "uniform",
                )
                self.assertEqual(pet._current_portrait, "a")
                self.assertEqual(pet._current_outfit, "uniform")
                self.assertLessEqual(
                    abs(pet.geometry().center().x() - previous_center_x),
                    1,
                )
                self.assertEqual(pet.geometry().bottom(), previous_bottom)
                pet.apply_settings(settings)
                self.assertEqual(pet._current_portrait, "a")
                self.assertEqual(
                    pet._current_layers,
                    layers_for("a", "高兴", "uniform"),
                )

                outfit_reply = parse_character_reply(
                    '{"outfit":"sleepwear","sentences":['
                    '{"zh":"晚安。","ja":"お休みじゃ。",'
                    '"emotion":"平静","portrait":"b"}]}'
                )
                with patch.object(pet, "_play_next_sentence") as play_next:
                    pet._on_reply(
                        pet._generation,
                        ConversationResult(
                            reply=outfit_reply,
                            audio_paths=[None],
                            user_text="换上睡衣",
                            is_user_message=True,
                            user_source="voice",
                        ),
                    )
                self.assertEqual(
                    pet.settings.character.outfit,
                    "sleepwear",
                )
                self.assertEqual(
                    json.loads(pet.history[-1]["content"])["outfit"],
                    "sleepwear",
                )
                self.assertEqual(pet.history[-2]["source"], "voice")
                play_next.assert_called_once()

                pet.history = [
                    {"role": "user", "content": "remember this"},
                    {"role": "assistant", "content": "remembered"},
                ]
                pet.history_store.save(pet.history)
                dialog.clear_history_requested.connect(pet.clear_history)
                with patch(
                    "aipet.ui.settings_dialog.QMessageBox.question",
                    return_value=QMessageBox.Yes,
                ):
                    dialog.clear_history_button.click()
                self.assertEqual(pet.history, [])
                self.assertEqual(pet.history_store.load(), [])
                self.assertIn("历史对话已清除", dialog.status_label.text())

                self.assertEqual(dialog.tabs.tabText(5), "其他")
                with (
                    patch(
                        "aipet.ui.settings_dialog.QMessageBox.question",
                        return_value=QMessageBox.Yes,
                    ),
                    patch(
                        "aipet.ui.settings_dialog.clear_runtime_cache",
                        return_value=CacheClearResult(
                            removed_files=3,
                            removed_bytes=1536,
                        ),
                    ) as clear_cache,
                ):
                    dialog.clear_cache_button.click()
                clear_cache.assert_called_once_with()
                self.assertIn("3 个缓存文件", dialog.status_label.text())
                self.assertIn("1.5 KiB", dialog.status_label.text())

                dialog._set_combo_data(dialog.mode_combo, "api")
                dialog._set_combo_data(dialog.api_provider, "openai")
                self.assertEqual(dialog.api_provider_stack.currentIndex(), 2)
                dialog.openai_key.setText("openai-key")
                dialog._set_combo_data(
                    dialog.vision_provider,
                    "ollama",
                )
                self.assertEqual(
                    dialog.vision_provider_stack.currentIndex(),
                    0,
                )
                dialog.vision_ollama_model.setCurrentText("local-vl")
                separated = dialog._form_settings()
                self.assertEqual(separated.api.provider, "openai")
                self.assertEqual(
                    separated.api.openai_chat_model,
                    "gpt-5.6-luna",
                )
                self.assertEqual(separated.vision.provider, "ollama")
                self.assertEqual(
                    separated.vision.ollama_model,
                    "local-vl",
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
                dialog.whisper_model_dir.setText(
                    str(Path(directory) / "whisper-download")
                )
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
                dialog.tts_engine_root.setText(
                    str(Path(directory) / "tts-engine-download")
                )
                dialog.tts_model_dir.setText(
                    str(Path(directory) / "tts-model-download")
                )
                missing_engine = TTSAssetState(
                    engine_root=None,
                    engine_ready=False,
                    gpt_weight=Path("murasame-gpt.ckpt"),
                    sovits_weight=Path("murasame-sovits.pth"),
                    reference_root=Path("reference_voices"),
                    reference_voices_ready=True,
                )
                with patch(
                    "aipet.ui.settings_dialog.QMessageBox.question",
                    return_value=QMessageBox.No,
                ):
                    dialog._on_tts_checked(missing_engine, False)
                self.assertEqual(
                    dialog._tts_engine_download_needed,
                    dialog._platform_runtime.capabilities.managed_archives,
                )
                self.assertEqual(
                    dialog.tts_download_button.isEnabled(),
                    dialog._platform_runtime.capabilities.managed_archives,
                )
                self.assertEqual(
                    dialog.tts_bootstrap_button.isEnabled(),
                    dialog._platform_runtime.capabilities.managed_tts_bootstrap,
                )
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
                explicit_engine = dialog.tts_engine_root.text()
                dialog._on_tts_checked(ready_engine, True)
                self.assertEqual(
                    dialog.tts_engine_root.text(),
                    explicit_engine,
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
                dialog._model_target = ("chat", "ollama", "deepseek")
                dialog._on_models_ready(["model-a", "model-b"])
                self.assertEqual(
                    dialog.ollama_chat_model.currentText(),
                    "custom-chat",
                )
                self.assertGreaterEqual(
                    dialog.ollama_chat_model.findText("model-a"),
                    0,
                )
                dialog._model_target = ("vision", "ollama", "ollama")
                dialog._on_models_ready(["vision-a", "vision-b"])
                self.assertGreaterEqual(
                    dialog.vision_ollama_model.findText("vision-a"),
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
                    pet._proactive_cooldown_until = 0
                    self.assertTrue(
                        pet._try_start_proactive_event("自动事件一")
                    )
                    self.assertFalse(
                        pet._try_start_proactive_event("自动事件二")
                    )
                    start_thread.assert_called_once_with(
                        "自动事件一",
                        role="system",
                    )

                    start_thread.reset_mock()
                    pet._proactive_cooldown_until = 0
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
                            change_summary="任务执行完成",
                        )
                    )
                    start_thread.assert_called_once()

                    pet._proactive_cooldown_until = 0
                    pet._on_screen_analysis(changed)
                    start_thread.assert_called_once()

                    pet._proactive_cooldown_until = 0
                    pet._on_screen_analysis(
                        ScreenAnalysis(
                            software="密码管理器",
                            activity="查看登录信息",
                            significant_change=True,
                            change_summary="切换到密码管理器",
                        )
                    )
                    self.assertEqual(start_thread.call_count, 2)
                    self.assertEqual(
                        [
                            entry.change_summary
                            for entry in pet.screen_memory_store.entries
                        ],
                        [
                            "从编辑器切换到浏览器",
                            "任务执行完成",
                            "从编辑器切换到浏览器",
                            "切换到密码管理器",
                        ],
                    )

                with patch.object(
                    pet,
                    "_try_start_proactive_event",
                ) as proactive_event:
                    pet._reset_idle_state()
                    with patch(
                        "aipet.ui.pet.get_idle_seconds",
                        return_value=(
                            pet.settings.idle.thinking_minutes * 60 + 1
                        ),
                    ):
                        pet.check_idle_state()
                    proactive_event.assert_called_once()

                    proactive_event.reset_mock()
                    pet._reset_idle_state()
                    with patch(
                        "aipet.ui.pet.get_idle_seconds",
                        return_value=(
                            pet.settings.idle.away_minutes * 60 + 1
                        ),
                    ):
                        pet.check_idle_state()
                    proactive_event.assert_called_once()

                    proactive_event.reset_mock()
                    pet.idle_away_triggered = True
                    pet.away_trigger_time = time.time() - 31
                    with patch(
                        "aipet.ui.pet.get_idle_seconds",
                        return_value=0,
                    ):
                        pet.check_idle_state()
                    proactive_event.assert_called_once()

                with patch.object(
                    dialog,
                    "_background_check_is_running",
                    return_value=True,
                ):
                    dialog.accept()
                self.assertEqual(dialog.result(), QDialog.Accepted)
                self.assertEqual(
                    dialog.result_settings().tts.engine_root,
                    explicit_engine,
                )
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
        subtle_scene_change = baseline.copy()
        subtle_scene_change.flat[:52] = 255
        obvious_change = np.full((54, 96), 255, dtype=np.uint8)

        self.assertFalse(Murasame._pixels_changed(baseline, unchanged))
        self.assertFalse(Murasame._pixels_changed(baseline, tiny_change))
        self.assertTrue(
            Murasame._pixels_changed(baseline, subtle_scene_change)
        )
        self.assertTrue(Murasame._pixels_changed(baseline, obvious_change))


if __name__ == "__main__":
    unittest.main()
