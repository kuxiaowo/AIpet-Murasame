from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from tool.backends import create_backend
from tool.config import (
    APISettings,
    AppSettings,
    CharacterSettings,
    DisplaySettings,
    IdleSettings,
    OllamaSettings,
    STTSettings,
    TTSSettings,
    VisionSettings,
    get_user_data_dir,
    load_personality,
)


class ModelListWorker(QThread):
    models_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            self.models_ready.emit(create_backend(self.settings).list_models())
        except Exception as exc:
            self.error.emit(str(exc))


class SettingsDialog(QDialog):
    """Visual configuration and personality creation window."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        first_run: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._original = settings.model_copy(deep=True)
        self._first_run = first_run
        self._model_worker: ModelListWorker | None = None
        self._result: AppSettings | None = None

        self.setWindowTitle(
            "AIpet Setup Studio" if first_run else "AIpet Settings Studio"
        )
        self.setMinimumSize(700, 650)
        self.resize(760, 720)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Configure the model backend, vision, voice, and character prompt. "
            "No local LoRA or chat Transformer is loaded."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        tabs = QTabWidget()
        tabs.addTab(self._build_models_tab(), "Models")
        tabs.addTab(self._build_character_tab(), "Character")
        tabs.addTab(self._build_automation_tab(), "Automation")
        root.addWidget(tabs, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_values(settings)
        self._update_backend_visibility()
        self._update_vision_compatibility()

    def _build_models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        mode_group = QGroupBox("Backend mode")
        mode_form = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Ollama (local service)", "ollama")
        self.mode_combo.addItem("Cloud API", "api")
        self.mode_combo.currentIndexChanged.connect(
            self._update_backend_visibility
        )
        mode_form.addRow("Mode", self.mode_combo)
        layout.addWidget(mode_group)

        self.backend_stack = QStackedWidget()
        self.backend_stack.addWidget(self._build_ollama_panel())
        self.backend_stack.addWidget(self._build_api_panel())
        layout.addWidget(self.backend_stack)

        test_row = QHBoxLayout()
        self.fetch_models_button = QPushButton("Test connection & list models")
        self.fetch_models_button.clicked.connect(self._fetch_models)
        test_row.addWidget(self.fetch_models_button)
        test_row.addStretch(1)
        layout.addLayout(test_row)
        layout.addStretch(1)
        return page

    def _build_ollama_panel(self) -> QWidget:
        panel = QGroupBox("Ollama")
        form = QFormLayout(panel)
        self.ollama_url = QLineEdit()
        self.ollama_chat_model = self._editable_combo()
        self.ollama_vision_model = self._editable_combo()
        self.ollama_context_window = self._spinbox(2_048, 131_072)
        self.ollama_context_window.setSingleStep(1_024)
        self.ollama_timeout = self._spinbox(10, 600, " seconds")
        self.ollama_keep_alive = QLineEdit()
        form.addRow("Server URL", self.ollama_url)
        form.addRow("Chat model", self.ollama_chat_model)
        form.addRow("Vision model", self.ollama_vision_model)
        form.addRow("Context window", self.ollama_context_window)
        form.addRow("Request timeout", self.ollama_timeout)
        form.addRow("Keep alive", self.ollama_keep_alive)
        return panel

    def _build_api_panel(self) -> QWidget:
        panel = QGroupBox("OpenAI-compatible cloud API")
        layout = QVBoxLayout(panel)
        provider_form = QFormLayout()
        self.api_provider = QComboBox()
        self.api_provider.addItem("DeepSeek", "deepseek")
        self.api_provider.addItem("Alibaba Cloud Model Studio", "aliyun")
        self.api_provider.currentIndexChanged.connect(
            self._update_api_provider
        )
        provider_form.addRow("Provider", self.api_provider)
        layout.addLayout(provider_form)

        self.api_provider_stack = QStackedWidget()
        self.api_provider_stack.addWidget(self._build_deepseek_panel())
        self.api_provider_stack.addWidget(self._build_aliyun_panel())
        layout.addWidget(self.api_provider_stack)

        common_form = QFormLayout()
        self.api_timeout = self._spinbox(10, 600, " seconds")
        common_form.addRow("Request timeout", self.api_timeout)
        layout.addLayout(common_form)
        return panel

    def _build_deepseek_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.deepseek_key = self._password_field()
        self.deepseek_url = QLineEdit()
        self.deepseek_chat_model = self._editable_combo()
        form.addRow("API key / DEEPSEEK_API_KEY", self.deepseek_key)
        form.addRow("Base URL", self.deepseek_url)
        form.addRow("Chat model", self.deepseek_chat_model)
        note = QLabel("DeepSeek currently provides chat here; vision is disabled.")
        note.setWordWrap(True)
        form.addRow(note)
        return panel

    def _build_aliyun_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.aliyun_key = self._password_field()
        self.aliyun_url = QLineEdit()
        self.aliyun_chat_model = self._editable_combo()
        self.aliyun_vision_model = self._editable_combo()
        form.addRow("API key / DASHSCOPE_API_KEY", self.aliyun_key)
        form.addRow("Base URL", self.aliyun_url)
        form.addRow("Chat model", self.aliyun_chat_model)
        form.addRow("Vision model", self.aliyun_vision_model)
        return panel

    def _build_character_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        identity = QGroupBox("Identity")
        identity_form = QFormLayout(identity)
        self.user_name = QLineEdit()
        self.portrait = QComboBox()
        self.portrait.addItem("Portrait A", "a")
        self.portrait.addItem("Portrait B", "b")
        identity_form.addRow("User name", self.user_name)
        identity_form.addRow("Portrait set", self.portrait)
        layout.addWidget(identity)

        prompt_group = QGroupBox("Personality prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_help = QLabel(
            "This prompt is the personality layer. The application adds the "
            "structured JSON contract automatically, so do not add output "
            "format instructions here."
        )
        prompt_help.setWordWrap(True)
        prompt_layout.addWidget(prompt_help)
        self.personality_prompt = QPlainTextEdit()
        self.personality_prompt.setPlaceholderText(
            "Describe the character, speaking style, relationship, and boundaries…"
        )
        prompt_layout.addWidget(self.personality_prompt, 1)
        import_button = QPushButton("Import prompt from text file…")
        import_button.clicked.connect(self._import_prompt)
        prompt_layout.addWidget(import_button)
        layout.addWidget(prompt_group, 1)
        return page

    def _build_automation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        vision_group = QGroupBox("Screen vision")
        vision_form = QFormLayout(vision_group)
        self.vision_enabled = QCheckBox("Analyze the selected screen periodically")
        self.vision_interval = self._spinbox(10, 86_400, " seconds")
        self.vision_compatibility = QLabel()
        self.vision_compatibility.setWordWrap(True)
        vision_form.addRow(self.vision_enabled)
        vision_form.addRow("Interval", self.vision_interval)
        vision_form.addRow(self.vision_compatibility)
        layout.addWidget(vision_group)

        speech_group = QGroupBox("Speech")
        speech_form = QFormLayout(speech_group)
        self.tts_enabled = QCheckBox("Use GPT-SoVITS-compatible TTS")
        self.tts_url = QLineEdit()
        self.tts_reference_root = QLineEdit()
        self.tts_timeout = self._spinbox(10, 900, " seconds")
        self.stt_enabled = QCheckBox("Hold Caps Lock for speech input")
        self.stt_model = QLineEdit()
        self.stt_device = QComboBox()
        self.stt_device.addItems(["auto", "cuda", "cpu"])
        speech_form.addRow(self.tts_enabled)
        speech_form.addRow("TTS endpoint", self.tts_url)
        speech_form.addRow("Remote reference root", self.tts_reference_root)
        speech_form.addRow("TTS timeout", self.tts_timeout)
        speech_form.addRow(self.stt_enabled)
        speech_form.addRow("Whisper model", self.stt_model)
        speech_form.addRow("STT device", self.stt_device)
        layout.addWidget(speech_group)

        behavior_group = QGroupBox("Display and idle behavior")
        behavior_form = QFormLayout(behavior_group)
        self.screen_index = self._spinbox(0, 32)
        self.portrait_ratio = QDoubleSpinBox()
        self.portrait_ratio.setRange(0.2, 1.0)
        self.portrait_ratio.setSingleStep(0.05)
        self.portrait_ratio.setDecimals(2)
        self.thinking_minutes = self._spinbox(1, 1_440, " minutes")
        self.away_minutes = self._spinbox(2, 1_440, " minutes")
        self.history_limit = self._spinbox(4, 200, " messages")
        behavior_form.addRow("Screen index", self.screen_index)
        behavior_form.addRow("Portrait height ratio", self.portrait_ratio)
        behavior_form.addRow("Thinking reminder", self.thinking_minutes)
        behavior_form.addRow("Away reminder", self.away_minutes)
        behavior_form.addRow("Conversation memory", self.history_limit)
        layout.addWidget(behavior_group)
        layout.addStretch(1)
        return page

    @staticmethod
    def _editable_combo() -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        return combo

    @staticmethod
    def _password_field() -> QLineEdit:
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setPlaceholderText("Leave blank when using the environment variable")
        return field

    @staticmethod
    def _spinbox(minimum: int, maximum: int, suffix: str = "") -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setSuffix(suffix)
        return spinbox

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_editable_combo(combo: QComboBox, value: str) -> None:
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def _load_values(self, settings: AppSettings) -> None:
        self._set_combo_data(self.mode_combo, settings.mode)
        self.ollama_url.setText(settings.ollama.base_url)
        self._set_editable_combo(
            self.ollama_chat_model,
            settings.ollama.chat_model,
        )
        self._set_editable_combo(
            self.ollama_vision_model,
            settings.ollama.vision_model,
        )
        self.ollama_timeout.setValue(settings.ollama.timeout_seconds)
        self.ollama_context_window.setValue(settings.ollama.context_window)
        self.ollama_keep_alive.setText(settings.ollama.keep_alive)

        self._set_combo_data(self.api_provider, settings.api.provider)
        self.deepseek_key.setText(settings.api.deepseek_api_key)
        self.deepseek_url.setText(settings.api.deepseek_base_url)
        self._set_editable_combo(
            self.deepseek_chat_model,
            settings.api.deepseek_chat_model,
        )
        self.aliyun_key.setText(settings.api.aliyun_api_key)
        self.aliyun_url.setText(settings.api.aliyun_base_url)
        self._set_editable_combo(
            self.aliyun_chat_model,
            settings.api.aliyun_chat_model,
        )
        self._set_editable_combo(
            self.aliyun_vision_model,
            settings.api.aliyun_vision_model,
        )
        self.api_timeout.setValue(settings.api.timeout_seconds)

        self.user_name.setText(settings.character.user_name)
        self._set_combo_data(self.portrait, settings.character.portrait)
        try:
            self.personality_prompt.setPlainText(load_personality(settings))
        except OSError:
            self.personality_prompt.clear()

        self.vision_enabled.setChecked(settings.vision.enabled)
        self.vision_interval.setValue(settings.vision.interval_seconds)
        self.tts_enabled.setChecked(settings.tts.enabled)
        self.tts_url.setText(settings.tts.base_url)
        self.tts_reference_root.setText(settings.tts.remote_reference_root)
        self.tts_timeout.setValue(settings.tts.timeout_seconds)
        self.stt_enabled.setChecked(settings.stt.enabled)
        self.stt_model.setText(settings.stt.model)
        self.stt_device.setCurrentText(settings.stt.device)
        self.screen_index.setValue(settings.display.screen_index)
        self.portrait_ratio.setValue(
            settings.display.portrait_screen_ratio
        )
        self.thinking_minutes.setValue(settings.idle.thinking_minutes)
        self.away_minutes.setValue(settings.idle.away_minutes)
        self.history_limit.setValue(settings.history_limit)

    def _update_backend_visibility(self) -> None:
        mode = self.mode_combo.currentData()
        self.backend_stack.setCurrentIndex(0 if mode == "ollama" else 1)
        self._update_vision_compatibility()

    def _update_api_provider(self) -> None:
        provider = self.api_provider.currentData()
        self.api_provider_stack.setCurrentIndex(
            0 if provider == "deepseek" else 1
        )
        self._update_vision_compatibility()

    def _update_vision_compatibility(self) -> None:
        if not hasattr(self, "vision_compatibility"):
            return
        unsupported = (
            self.mode_combo.currentData() == "api"
            and self.api_provider.currentData() == "deepseek"
        )
        self.vision_enabled.setEnabled(not unsupported)
        if unsupported:
            self.vision_enabled.setChecked(False)
            self.vision_compatibility.setText(
                "DeepSeek mode is chat-only. Choose Alibaba Cloud or Ollama "
                "to enable screen vision."
            )
        else:
            self.vision_compatibility.setText(
                "The configured vision model will receive periodic screenshots."
            )

    def _import_prompt(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Import personality prompt",
            str(Path.home()),
            "Text files (*.txt *.md);;All files (*)",
        )
        if not file_name:
            return
        try:
            self.personality_prompt.setPlainText(
                Path(file_name).read_text(encoding="utf-8")
            )
        except OSError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    def _form_settings(self) -> AppSettings:
        personality_path = get_user_data_dir() / "personality.txt"
        return AppSettings(
            mode=self.mode_combo.currentData(),
            ollama=OllamaSettings(
                base_url=self.ollama_url.text().strip(),
                chat_model=self.ollama_chat_model.currentText().strip(),
                vision_model=self.ollama_vision_model.currentText().strip(),
                context_window=self.ollama_context_window.value(),
                timeout_seconds=self.ollama_timeout.value(),
                keep_alive=self.ollama_keep_alive.text().strip(),
            ),
            api=APISettings(
                provider=self.api_provider.currentData(),
                deepseek_api_key=self.deepseek_key.text().strip(),
                aliyun_api_key=self.aliyun_key.text().strip(),
                deepseek_base_url=self.deepseek_url.text().strip(),
                aliyun_base_url=self.aliyun_url.text().strip(),
                deepseek_chat_model=(
                    self.deepseek_chat_model.currentText().strip()
                ),
                aliyun_chat_model=(
                    self.aliyun_chat_model.currentText().strip()
                ),
                aliyun_vision_model=(
                    self.aliyun_vision_model.currentText().strip()
                ),
                timeout_seconds=self.api_timeout.value(),
            ),
            vision=VisionSettings(
                enabled=self.vision_enabled.isChecked(),
                interval_seconds=self.vision_interval.value(),
            ),
            tts=TTSSettings(
                enabled=self.tts_enabled.isChecked(),
                base_url=self.tts_url.text().strip(),
                remote_reference_root=self.tts_reference_root.text().strip(),
                timeout_seconds=self.tts_timeout.value(),
            ),
            stt=STTSettings(
                enabled=self.stt_enabled.isChecked(),
                model=self.stt_model.text().strip(),
                device=self.stt_device.currentText(),
            ),
            character=CharacterSettings(
                user_name=self.user_name.text().strip(),
                portrait=self.portrait.currentData(),
                personality_file=str(personality_path),
            ),
            display=DisplaySettings(
                screen_index=self.screen_index.value(),
                portrait_screen_ratio=self.portrait_ratio.value(),
            ),
            idle=IdleSettings(
                thinking_minutes=self.thinking_minutes.value(),
                away_minutes=self.away_minutes.value(),
            ),
            history_limit=self.history_limit.value(),
        )

    def _fetch_models(self) -> None:
        try:
            settings = self._form_settings()
        except ValidationError as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return

        self.fetch_models_button.setEnabled(False)
        self.status_label.setText("Connecting…")
        worker = ModelListWorker(settings, self)
        self._model_worker = worker
        worker.models_ready.connect(self._on_models_ready)
        worker.error.connect(self._on_models_error)
        worker.finished.connect(lambda: self._finish_model_worker(worker))
        worker.start()

    def _finish_model_worker(self, worker: ModelListWorker) -> None:
        self.fetch_models_button.setEnabled(True)
        if self._model_worker is worker:
            self._model_worker = None
        worker.deleteLater()

    def _on_models_ready(self, models: list[str]) -> None:
        if not models:
            self.status_label.setText(
                "Connection succeeded, but the service returned no models."
            )
            return
        targets: list[QComboBox]
        if self.mode_combo.currentData() == "ollama":
            targets = [self.ollama_chat_model, self.ollama_vision_model]
        elif self.api_provider.currentData() == "aliyun":
            targets = [self.aliyun_chat_model, self.aliyun_vision_model]
        else:
            targets = [self.deepseek_chat_model]
        for combo in targets:
            selected = combo.currentText()
            combo.clear()
            combo.addItems(models)
            combo.setCurrentText(selected if selected in models else models[0])
        self.status_label.setText(
            f"Connection succeeded. Found {len(models)} model(s)."
        )

    def _on_models_error(self, message: str) -> None:
        self.status_label.setText(f"Connection failed: {message}")

    def accept(self) -> None:
        if self._model_worker is not None and self._model_worker.isRunning():
            QMessageBox.information(
                self,
                "Connection test is running",
                "Please wait for the current connection test to finish.",
            )
            return
        prompt = self.personality_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(
                self,
                "Missing personality",
                "Please provide a personality prompt.",
            )
            return
        try:
            settings = self._form_settings()
        except ValidationError as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return
        if settings.requires_api_key():
            QMessageBox.warning(
                self,
                "Missing API key",
                "Enter an API key or set the provider environment variable.",
            )
            return

        personality_path = settings.personality_path()
        try:
            personality_path.parent.mkdir(parents=True, exist_ok=True)
            personality_path.write_text(prompt + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return

        self._result = settings
        super().accept()

    def reject(self) -> None:
        if self._model_worker is not None and self._model_worker.isRunning():
            QMessageBox.information(
                self,
                "Connection test is running",
                "Please wait for the current connection test to finish.",
            )
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._model_worker is not None and self._model_worker.isRunning():
            event.ignore()
            QMessageBox.information(
                self,
                "Connection test is running",
                "Please wait for the current connection test to finish.",
            )
            return
        super().closeEvent(event)

    def result_settings(self) -> AppSettings:
        if self._result is None:
            return self._original.model_copy(deep=True)
        return self._result.model_copy(deep=True)
