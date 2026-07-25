from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from classes.download_manager import (
    TTS_JOB_ID,
    DownloadManager,
    DownloadSnapshot,
    whisper_job_id,
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
from tool.network import is_loopback_url
from tool.tts_assets import (
    TTSAssetState,
    configure_local_tts_weights,
    locate_tts_assets,
    managed_tts_model_dir,
    tts_service_is_reachable,
)
from tool.tts_service import (
    TTSServiceError,
    get_tts_service_manager,
)
from tool.whisper_models import (
    WHISPER_MODELS,
    find_local_model,
    model_repository,
)


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "title_setup": "AIpet Initial Setup",
        "title_settings": "AIpet Settings",
        "intro": (
            "Configure the model backend, vision, voice, and character prompt. "
            "No local LoRA or chat Transformer is loaded."
        ),
        "language": "Language / 语言",
        "tab_models": "Models",
        "tab_character": "Character",
        "tab_automation": "Automation",
        "backend_group": "Backend mode",
        "mode": "Mode",
        "mode_ollama": "Ollama (local service)",
        "mode_api": "Cloud API",
        "ollama_group": "Ollama",
        "server_url": "Server URL",
        "chat_model": "Chat model",
        "vision_model": "Vision model",
        "context_window": "Context window",
        "request_timeout": "Request timeout",
        "keep_alive": "Keep alive",
        "api_group": "OpenAI-compatible cloud API",
        "provider": "Provider",
        "provider_aliyun": "Alibaba Cloud Model Studio",
        "deepseek_api_key": "API key / DEEPSEEK_API_KEY",
        "aliyun_api_key": "API key / DASHSCOPE_API_KEY",
        "base_url": "Base URL",
        "deepseek_thinking": "Enable DeepSeek thinking mode (slower)",
        "deepseek_note": (
            "DeepSeek V4 is used for chat. This provider does not supply the "
            "screen-vision model in AIpet."
        ),
        "load_models": "Test connection & load models",
        "model_list_help": (
            "Uses Ollama /api/tags or the provider's /models endpoint. "
            "Model fields stay editable for custom or unlisted IDs."
        ),
        "identity_group": "Identity",
        "user_name": "User name",
        "portrait_set": "Portrait set",
        "portrait_a": "Portrait A",
        "portrait_b": "Portrait B",
        "prompt_group": "Personality prompt",
        "prompt_help": (
            "This is the personality layer. AIpet adds the structured JSON "
            "contract automatically, so do not add output-format rules here."
        ),
        "prompt_placeholder": (
            "Describe the character, speaking style, relationship, and boundaries…"
        ),
        "import_prompt": "Import prompt from text file…",
        "vision_group": "Screen vision",
        "vision_enabled": "Analyze the selected screen periodically",
        "interval": "Interval",
        "vision_supported": (
            "The configured vision model will receive periodic screenshots."
        ),
        "vision_unsupported": (
            "DeepSeek mode is chat-only. Choose Alibaba Cloud or Ollama "
            "to enable screen vision."
        ),
        "speech_group": "Speech",
        "tts_enabled": "Use GPT-SoVITS-compatible TTS",
        "tts_endpoint": "TTS endpoint",
        "remote_reference_root": "Remote reference root",
        "tts_timeout": "TTS timeout",
        "tts_engine_root": "GPT-SoVITS directory",
        "tts_model_dir": "Voice model directory",
        "browse": "Browse…",
        "tts_disabled": (
            "Enable TTS to check the engine, voice model, references, and service."
        ),
        "tts_invalid": "Enter a valid TTS endpoint before checking it.",
        "tts_checking": "Checking GPT-SoVITS components…",
        "tts_ready_online": "Voice model is ready and the TTS service is online.",
        "tts_ready_offline": (
            "Voice model is ready, but the TTS service is not running."
        ),
        "tts_service_start": "Start TTS service",
        "tts_service_stop": "Stop TTS service",
        "tts_service_online": "TTS service online",
        "tts_service_locating": "Locating the GPT-SoVITS runtime…",
        "tts_service_starting": "Starting the GPT-SoVITS process…",
        "tts_service_waiting": "Waiting for the TTS API to become ready…",
        "tts_service_waiting_existing": (
            "Another request is starting the TTS service; waiting…"
        ),
        "tts_service_loading_weights": "Loading the character voice weights…",
        "tts_service_stopping": "Stopping the TTS service…",
        "tts_service_started": "The TTS service is ready.",
        "tts_service_stopped": "The TTS service has stopped.",
        "tts_service_failed": "TTS service operation failed: {message}",
        "tts_model_missing": "The Murasame voice model is missing.",
        "tts_engine_missing": (
            "The voice model is ready, but the GPT-SoVITS directory was not found."
        ),
        "tts_engine_incomplete": (
            "The voice model is ready, but GPT-SoVITS base assets are incomplete."
        ),
        "tts_references_missing": "One or more reference voice files are missing.",
        "tts_external_online": "The external TTS endpoint is reachable.",
        "tts_external_offline": "The external TTS endpoint is not reachable.",
        "tts_download_consent_title": "Download Murasame voice model",
        "tts_download_consent_body": (
            "Download the GPT and SoVITS character weights and six reference "
            "voices (about 231 MB) from ModelScope? The assets are intended "
            "for non-commercial, educational use and reference proprietary "
            "character material."
        ),
        "tts_download_consent_body_with_engine": (
            "GPT-SoVITS was not detected. Download the complete engine package "
            "selected for your NVIDIA GPU together with the character weights "
            "and reference voices? The download is about 8–9 GB and requires "
            "additional free space while extracting. The assets are intended "
            "for non-commercial, educational use."
        ),
        "tts_download": "Download voice model",
        "tts_preparing": "Preparing the TTS download: {detail}",
        "tts_downloading": "Downloading the Murasame voice model: {detail}",
        "tts_checking_files": "Checking downloaded files: {detail}",
        "tts_extracting": "Extracting GPT-SoVITS: {detail}",
        "tts_installing": "Installing GPT-SoVITS: {detail}",
        "tts_cleaning": "Cleaning temporary files: {detail}",
        "tts_downloaded": "Voice model download completed: {path}",
        "tts_download_failed": "Voice model download failed: {message}",
        "download_files": "files",
        "download_steps": "steps",
        "stt_enabled": "Hold Caps Lock for speech input",
        "whisper_model": "Whisper model",
        "stt_device": "STT device",
        "whisper_download": "Download model",
        "whisper_disabled": (
            "Enable speech input to check whether the selected model is cached."
        ),
        "whisper_checking": "Checking the local faster-whisper cache…",
        "whisper_installed": "Available locally: {path}",
        "whisper_missing": (
            "Not found locally. Downloading requires faster-whisper and an "
            "internet connection."
        ),
        "whisper_downloading": (
            "Downloading {model}: {detail}"
        ),
        "whisper_preparing": "Preparing {model}: {detail}",
        "whisper_verifying": "Checking {model}: {detail}",
        "whisper_downloaded": "Download complete. Available locally: {path}",
        "whisper_download_failed": "Download failed: {message}",
        "behavior_group": "Display and idle behavior",
        "screen_index": "Screen index",
        "portrait_ratio": "Portrait height ratio",
        "thinking_reminder": "Thinking reminder",
        "away_reminder": "Away reminder",
        "conversation_memory": "Conversation memory",
        "password_placeholder": (
            "Leave blank when using the environment variable"
        ),
        "seconds": " seconds",
        "minutes": " minutes",
        "messages": " messages",
        "save": "Save",
        "cancel": "Cancel",
        "connecting": "Connecting to the model-list endpoint…",
        "models_empty": (
            "Connection succeeded, but the service returned no models. "
            "You can still type a model ID manually."
        ),
        "models_found": (
            "Connection succeeded. Loaded {count} model(s); "
            "manual input remains enabled."
        ),
        "connection_failed": (
            "Model-list request failed: {message}\n"
            "The current model ID was kept and can be edited manually."
        ),
        "import_title": "Import personality prompt",
        "text_filter": "Text files (*.txt *.md);;All files (*)",
        "import_failed": "Import failed",
        "invalid_settings": "Invalid settings",
        "test_running_title": "Connection test is running",
        "test_running_body": (
            "Please wait for the current connection test to finish."
        ),
        "missing_personality": "Missing personality",
        "missing_personality_body": "Please provide a personality prompt.",
        "missing_key": "Missing API key",
        "missing_key_body": (
            "Enter an API key or set the provider environment variable."
        ),
        "save_failed": "Save failed",
        "download_preparing": "Preparing download…",
    },
    "zh-CN": {
        "title_setup": "AIpet 初始设置",
        "title_settings": "AIpet 设置",
        "intro": (
            "配置模型后端、视觉、语音和角色提示词。"
            "程序不会加载本地 LoRA 或聊天 Transformer。"
        ),
        "language": "界面语言 / Language",
        "tab_models": "模型",
        "tab_character": "角色",
        "tab_automation": "自动行为",
        "backend_group": "后端模式",
        "mode": "模式",
        "mode_ollama": "Ollama（本地服务）",
        "mode_api": "云端 API",
        "ollama_group": "Ollama",
        "server_url": "服务地址",
        "chat_model": "对话模型",
        "vision_model": "视觉模型",
        "context_window": "上下文长度",
        "request_timeout": "请求超时",
        "keep_alive": "模型驻留时间",
        "api_group": "OpenAI 兼容云端 API",
        "provider": "服务商",
        "provider_aliyun": "阿里云百炼",
        "deepseek_api_key": "API Key / DEEPSEEK_API_KEY",
        "aliyun_api_key": "API Key / DASHSCOPE_API_KEY",
        "base_url": "基础地址",
        "deepseek_thinking": "启用 DeepSeek 思考模式（响应更慢）",
        "deepseek_note": (
            "DeepSeek V4 用于对话；AIpet 当前不使用该服务商提供屏幕视觉模型。"
        ),
        "load_models": "测试连接并加载模型",
        "model_list_help": (
            "Ollama 使用 /api/tags，云端服务使用 /models。"
            "下拉框始终可以手动输入自定义或未列出的模型 ID。"
        ),
        "identity_group": "身份",
        "user_name": "用户名称",
        "portrait_set": "立绘组",
        "portrait_a": "立绘 A",
        "portrait_b": "立绘 B",
        "prompt_group": "人格提示词",
        "prompt_help": (
            "这里仅描述人格。AIpet 会自动添加结构化 JSON 规则，"
            "请不要在这里重复编写输出格式。"
        ),
        "prompt_placeholder": "描述角色身份、说话风格、关系和行为边界……",
        "import_prompt": "从文本文件导入提示词…",
        "vision_group": "屏幕视觉",
        "vision_enabled": "定期分析所选屏幕",
        "interval": "间隔",
        "vision_supported": "配置的视觉模型将接收定期屏幕截图。",
        "vision_unsupported": (
            "DeepSeek 模式当前只支持对话；请改用阿里云或 Ollama 启用屏幕视觉。"
        ),
        "speech_group": "语音",
        "tts_enabled": "使用 GPT-SoVITS 兼容 TTS",
        "tts_endpoint": "TTS 地址",
        "remote_reference_root": "远程参考音频根目录",
        "tts_timeout": "TTS 超时",
        "tts_engine_root": "GPT-SoVITS 目录",
        "tts_model_dir": "角色语音模型目录",
        "browse": "浏览…",
        "tts_disabled": "启用 TTS 后，将检查引擎、角色模型、参考音频和服务。",
        "tts_invalid": "请先填写有效的 TTS 地址。",
        "tts_checking": "正在检查 GPT-SoVITS 组件……",
        "tts_ready_online": "角色语音模型完整，TTS 服务在线。",
        "tts_ready_offline": "角色语音模型完整，但 TTS 服务尚未运行。",
        "tts_service_start": "启动 TTS 服务",
        "tts_service_stop": "停止 TTS 服务",
        "tts_service_online": "TTS 服务在线",
        "tts_service_locating": "正在定位 GPT-SoVITS 运行环境……",
        "tts_service_starting": "正在启动 GPT-SoVITS 进程……",
        "tts_service_waiting": "正在等待 TTS API 就绪……",
        "tts_service_waiting_existing": "已有请求正在启动 TTS 服务，正在等待……",
        "tts_service_loading_weights": "正在加载角色语音权重……",
        "tts_service_stopping": "正在停止 TTS 服务……",
        "tts_service_started": "TTS 服务已就绪。",
        "tts_service_stopped": "TTS 服务已停止。",
        "tts_service_failed": "TTS 服务操作失败：{message}",
        "tts_model_missing": "本地缺少丛雨角色语音模型。",
        "tts_engine_missing": "角色语音模型完整，但没有找到 GPT-SoVITS 目录。",
        "tts_engine_incomplete": (
            "角色语音模型完整，但 GPT-SoVITS 基础资源不完整。"
        ),
        "tts_references_missing": "一项或多项参考语音文件缺失。",
        "tts_external_online": "外部 TTS 接口可以连接。",
        "tts_external_offline": "外部 TTS 接口当前无法连接。",
        "tts_download_consent_title": "下载丛雨语音模型",
        "tts_download_consent_body": (
            "是否从 ModelScope 下载 GPT、SoVITS 角色权重及六组参考音频"
            "（约 231 MB）？这些资源仅用于非商业和学习用途，"
            "并涉及角色专有素材。"
        ),
        "tts_download_consent_body_with_engine": (
            "未检测到 GPT-SoVITS。是否根据 NVIDIA 显卡型号自动选择并下载"
            "完整引擎，同时下载角色权重和参考音频？下载量约 8～9 GB，"
            "解压时还需要额外可用空间。这些资源仅用于非商业和学习用途。"
        ),
        "tts_download": "下载角色语音模型",
        "tts_preparing": "正在准备 TTS 下载：{detail}",
        "tts_downloading": "正在下载丛雨语音模型：{detail}",
        "tts_checking_files": "正在校验已下载文件：{detail}",
        "tts_extracting": "正在解压 GPT-SoVITS：{detail}",
        "tts_installing": "正在安装 GPT-SoVITS：{detail}",
        "tts_cleaning": "正在清理临时文件：{detail}",
        "tts_downloaded": "角色语音模型下载完成：{path}",
        "tts_download_failed": "角色语音模型下载失败：{message}",
        "download_files": "个文件",
        "download_steps": "个步骤",
        "stt_enabled": "长按 Caps Lock 进行语音输入",
        "whisper_model": "Whisper 模型",
        "stt_device": "语音识别设备",
        "whisper_download": "下载模型",
        "whisper_disabled": "启用语音输入后，将检测所选模型是否已缓存在本地。",
        "whisper_checking": "正在检查本地 faster-whisper 缓存……",
        "whisper_installed": "本地已安装：{path}",
        "whisper_missing": (
            "本地未找到。下载需要已安装 faster-whisper，并且网络可用。"
        ),
        "whisper_downloading": "正在下载 {model}：{detail}",
        "whisper_preparing": "正在准备 {model}：{detail}",
        "whisper_verifying": "正在校验 {model}：{detail}",
        "whisper_downloaded": "下载完成，本地路径：{path}",
        "whisper_download_failed": "下载失败：{message}",
        "behavior_group": "显示与空闲行为",
        "screen_index": "屏幕编号",
        "portrait_ratio": "立绘高度比例",
        "thinking_reminder": "思考提醒",
        "away_reminder": "离开提醒",
        "conversation_memory": "对话记忆",
        "password_placeholder": "使用环境变量时留空",
        "seconds": " 秒",
        "minutes": " 分钟",
        "messages": " 条消息",
        "save": "保存",
        "cancel": "取消",
        "connecting": "正在连接模型列表接口……",
        "models_empty": (
            "连接成功，但服务没有返回模型。仍然可以手动输入模型 ID。"
        ),
        "models_found": "连接成功，已加载 {count} 个模型；仍可手动输入。",
        "connection_failed": (
            "模型列表请求失败：{message}\n"
            "当前模型 ID 已保留，可以继续手动编辑。"
        ),
        "import_title": "导入人格提示词",
        "text_filter": "文本文件 (*.txt *.md);;所有文件 (*)",
        "import_failed": "导入失败",
        "invalid_settings": "设置无效",
        "test_running_title": "连接测试正在运行",
        "test_running_body": "请等待当前连接测试结束。",
        "missing_personality": "缺少人格提示词",
        "missing_personality_body": "请填写人格提示词。",
        "missing_key": "缺少 API Key",
        "missing_key_body": "请输入 API Key，或设置对应的环境变量。",
        "save_failed": "保存失败",
        "download_preparing": "正在准备下载……",
    },
}


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


class WhisperModelCheckWorker(QThread):
    checked = pyqtSignal(str, str)

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def run(self) -> None:
        path = find_local_model(self.model_name) or ""
        self.checked.emit(self.model_name, path)


class TTSCheckWorker(QThread):
    checked = pyqtSignal(object, bool)

    def __init__(self, settings: TTSSettings, parent=None):
        super().__init__(parent)
        self.settings = settings.model_copy(deep=True)

    def run(self) -> None:
        state = locate_tts_assets(
            configured_engine_root=self.settings.engine_root,
            configured_model_dir=self.settings.model_dir,
        )
        reachable = tts_service_is_reachable(self.settings.base_url)
        self.checked.emit(state, reachable)


class TTSServiceWorker(QThread):
    stage_changed = pyqtSignal(str)
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        settings: TTSSettings,
        action: str,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings.model_copy(deep=True)
        self.action = action

    def run(self) -> None:
        manager = get_tts_service_manager()
        try:
            if self.action == "stop":
                manager.stop()
                self.succeeded.emit("stopped")
                return

            state = locate_tts_assets(
                configured_engine_root=self.settings.engine_root,
                configured_model_dir=self.settings.model_dir,
            )
            if not state.model_ready:
                raise TTSServiceError(
                    "The Murasame voice weights are incomplete."
                )
            manager.ensure_running(
                self.settings,
                state=state,
                progress=self.stage_changed.emit,
            )
            self.stage_changed.emit("loading_weights")
            configure_local_tts_weights(
                self.settings.base_url,
                state,
                self.settings.timeout_seconds,
            )
            self.succeeded.emit("started")
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    """Visual bilingual configuration and personality creation window."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        first_run: bool = False,
        download_manager: DownloadManager | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._original = settings.model_copy(deep=True)
        self._first_run = first_run
        self._model_worker: ModelListWorker | None = None
        self._model_target: tuple[str, str] | None = None
        self._whisper_check_worker: WhisperModelCheckWorker | None = None
        self._pending_whisper_model: str | None = None
        self._tts_check_worker: TTSCheckWorker | None = None
        self._tts_service_worker: TTSServiceWorker | None = None
        self._tts_service_error: str | None = None
        self._tts_service_button_mode = "start"
        self._pending_tts_check = False
        self._tts_download_prompted = False
        self._tts_engine_download_needed = False
        self._result: AppSettings | None = None
        self.download_manager = download_manager or DownloadManager(
            QApplication.instance()
        )
        self._form_labels: dict[str, list[QLabel]] = {}
        self._status_key: str | None = None
        self._status_values: dict[str, object] = {}
        self._whisper_status_key = "whisper_disabled"
        self._whisper_status_values: dict[str, object] = {}
        self._tts_status_key = "tts_disabled"
        self._tts_status_values: dict[str, object] = {}

        self.setMinimumSize(700, 650)
        self.resize(760, 720)
        root = QVBoxLayout(self)

        self.intro_label = QLabel()
        self.intro_label.setWordWrap(True)
        root.addWidget(self.intro_label)

        language_form = QFormLayout()
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh-CN")
        language_form.addRow(self.language_label, self.language_combo)
        root.addLayout(language_form)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_models_tab(), "")
        self.tabs.addTab(self._build_character_tab(), "")
        self.tabs.addTab(self._build_automation_tab(), "")
        root.addWidget(self.tabs, 1)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._load_values(settings)
        self.language_combo.currentIndexChanged.connect(
            self._on_language_changed
        )
        self.stt_enabled.toggled.connect(self._update_whisper_state)
        self.stt_model.currentTextChanged.connect(self._update_whisper_state)
        self.tts_enabled.toggled.connect(self._update_tts_state)
        self.tts_url.editingFinished.connect(self._update_tts_state)
        self.tts_engine_root.editingFinished.connect(self._update_tts_state)
        self.tts_model_dir.editingFinished.connect(self._update_tts_state)
        self.download_manager.changed.connect(self._on_download_changed)
        self._update_backend_visibility()
        self._retranslate_ui()
        self._update_whisper_state()
        self._update_tts_state()

    def _add_row(
        self,
        form: QFormLayout,
        key: str,
        field: QWidget,
    ) -> None:
        label = QLabel()
        form.addRow(label, field)
        self._form_labels.setdefault(key, []).append(label)

    def _build_models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.backend_group = QGroupBox()
        mode_form = QFormLayout(self.backend_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("", "ollama")
        self.mode_combo.addItem("", "api")
        self.mode_combo.currentIndexChanged.connect(
            self._update_backend_visibility
        )
        self._add_row(mode_form, "mode", self.mode_combo)
        layout.addWidget(self.backend_group)

        self.backend_stack = QStackedWidget()
        self.backend_stack.addWidget(self._build_ollama_panel())
        self.backend_stack.addWidget(self._build_api_panel())
        layout.addWidget(self.backend_stack)

        test_row = QHBoxLayout()
        self.fetch_models_button = QPushButton()
        self.fetch_models_button.clicked.connect(self._fetch_models)
        test_row.addWidget(self.fetch_models_button)
        test_row.addStretch(1)
        layout.addLayout(test_row)
        self.model_list_help = QLabel()
        self.model_list_help.setWordWrap(True)
        layout.addWidget(self.model_list_help)
        layout.addStretch(1)
        return page

    def _build_ollama_panel(self) -> QWidget:
        self.ollama_group = QGroupBox()
        form = QFormLayout(self.ollama_group)
        self.ollama_url = QLineEdit()
        self.ollama_chat_model = self._editable_combo()
        self.ollama_vision_model = self._editable_combo()
        self.ollama_context_window = self._spinbox(2_048, 131_072)
        self.ollama_context_window.setSingleStep(1_024)
        self.ollama_timeout = self._spinbox(10, 600)
        self.ollama_keep_alive = QLineEdit()
        self._add_row(form, "server_url", self.ollama_url)
        self._add_row(form, "chat_model", self.ollama_chat_model)
        self._add_row(form, "vision_model", self.ollama_vision_model)
        self._add_row(form, "context_window", self.ollama_context_window)
        self._add_row(form, "request_timeout", self.ollama_timeout)
        self._add_row(form, "keep_alive", self.ollama_keep_alive)
        return self.ollama_group

    def _build_api_panel(self) -> QWidget:
        self.api_group = QGroupBox()
        layout = QVBoxLayout(self.api_group)
        provider_form = QFormLayout()
        self.api_provider = QComboBox()
        self.api_provider.addItem("DeepSeek", "deepseek")
        self.api_provider.addItem("", "aliyun")
        self.api_provider.currentIndexChanged.connect(
            self._update_api_provider
        )
        self._add_row(provider_form, "provider", self.api_provider)
        layout.addLayout(provider_form)

        self.api_provider_stack = QStackedWidget()
        self.api_provider_stack.addWidget(self._build_deepseek_panel())
        self.api_provider_stack.addWidget(self._build_aliyun_panel())
        layout.addWidget(self.api_provider_stack)

        common_form = QFormLayout()
        self.api_timeout = self._spinbox(10, 600)
        self._add_row(common_form, "request_timeout", self.api_timeout)
        layout.addLayout(common_form)
        return self.api_group

    def _build_deepseek_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.deepseek_key = self._password_field()
        self.deepseek_url = QLineEdit()
        self.deepseek_chat_model = self._editable_combo()
        self.deepseek_chat_model.addItems(
            ["deepseek-v4-flash", "deepseek-v4-pro"]
        )
        self.deepseek_thinking = QCheckBox()
        self._add_row(form, "deepseek_api_key", self.deepseek_key)
        self._add_row(form, "base_url", self.deepseek_url)
        self._add_row(form, "chat_model", self.deepseek_chat_model)
        form.addRow(self.deepseek_thinking)
        self.deepseek_note = QLabel()
        self.deepseek_note.setWordWrap(True)
        form.addRow(self.deepseek_note)
        return panel

    def _build_aliyun_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.aliyun_key = self._password_field()
        self.aliyun_url = QLineEdit()
        self.aliyun_chat_model = self._editable_combo()
        self.aliyun_vision_model = self._editable_combo()
        self._add_row(form, "aliyun_api_key", self.aliyun_key)
        self._add_row(form, "base_url", self.aliyun_url)
        self._add_row(form, "chat_model", self.aliyun_chat_model)
        self._add_row(form, "vision_model", self.aliyun_vision_model)
        return panel

    def _build_character_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.identity_group = QGroupBox()
        identity_form = QFormLayout(self.identity_group)
        self.user_name = QLineEdit()
        self.portrait = QComboBox()
        self.portrait.addItem("", "a")
        self.portrait.addItem("", "b")
        self._add_row(identity_form, "user_name", self.user_name)
        self._add_row(identity_form, "portrait_set", self.portrait)
        layout.addWidget(self.identity_group)

        self.prompt_group = QGroupBox()
        prompt_layout = QVBoxLayout(self.prompt_group)
        self.prompt_help = QLabel()
        self.prompt_help.setWordWrap(True)
        prompt_layout.addWidget(self.prompt_help)
        self.personality_prompt = QPlainTextEdit()
        prompt_layout.addWidget(self.personality_prompt, 1)
        self.import_button = QPushButton()
        self.import_button.clicked.connect(self._import_prompt)
        prompt_layout.addWidget(self.import_button)
        layout.addWidget(self.prompt_group, 1)
        return page

    def _build_automation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.vision_group = QGroupBox()
        vision_form = QFormLayout(self.vision_group)
        self.vision_enabled = QCheckBox()
        self.vision_interval = self._spinbox(10, 86_400)
        self.vision_compatibility = QLabel()
        self.vision_compatibility.setWordWrap(True)
        vision_form.addRow(self.vision_enabled)
        self._add_row(vision_form, "interval", self.vision_interval)
        vision_form.addRow(self.vision_compatibility)
        layout.addWidget(self.vision_group)

        self.speech_group = QGroupBox()
        speech_form = QFormLayout(self.speech_group)
        self.tts_enabled = QCheckBox()
        self.tts_url = QLineEdit()
        self.tts_reference_root = QLineEdit()
        self.tts_timeout = self._spinbox(10, 900)
        self.tts_engine_root = QLineEdit()
        self.tts_engine_browse = QPushButton()
        self.tts_engine_browse.clicked.connect(self._browse_tts_engine)
        self.tts_model_dir = QLineEdit()
        self.tts_model_browse = QPushButton()
        self.tts_model_browse.clicked.connect(self._browse_tts_model)
        self.tts_status = QLabel()
        self.tts_status.setWordWrap(True)
        self.tts_progress = QProgressBar()
        self.tts_progress.setTextVisible(True)
        self.tts_progress.hide()
        self.tts_extract_progress = QProgressBar()
        self.tts_extract_progress.setTextVisible(True)
        self.tts_extract_progress.hide()
        self.tts_download_button = QPushButton()
        self.tts_download_button.setEnabled(False)
        self.tts_download_button.clicked.connect(
            self._request_tts_download
        )
        self.tts_service_button = QPushButton()
        self.tts_service_button.setEnabled(False)
        self.tts_service_button.clicked.connect(
            self._toggle_tts_service
        )
        self.stt_enabled = QCheckBox()
        self.stt_model = self._editable_combo()
        self.stt_model.addItems(WHISPER_MODELS)
        self.stt_device = QComboBox()
        self.stt_device.addItems(["auto", "cuda", "cpu"])
        self.whisper_status = QLabel()
        self.whisper_status.setWordWrap(True)
        self.whisper_progress = QProgressBar()
        self.whisper_progress.setTextVisible(True)
        self.whisper_progress.hide()
        self.whisper_download_button = QPushButton()
        self.whisper_download_button.clicked.connect(
            self._download_whisper_model
        )
        speech_form.addRow(self.tts_enabled)
        self._add_row(speech_form, "tts_endpoint", self.tts_url)
        self._add_row(
            speech_form,
            "remote_reference_root",
            self.tts_reference_root,
        )
        self._add_row(speech_form, "tts_timeout", self.tts_timeout)
        self._add_row(
            speech_form,
            "tts_engine_root",
            self._path_picker(
                self.tts_engine_root,
                self.tts_engine_browse,
            ),
        )
        self._add_row(
            speech_form,
            "tts_model_dir",
            self._path_picker(
                self.tts_model_dir,
                self.tts_model_browse,
            ),
        )
        speech_form.addRow(self.tts_status)
        speech_form.addRow(self.tts_service_button)
        speech_form.addRow(self.tts_progress)
        speech_form.addRow(self.tts_extract_progress)
        speech_form.addRow(self.tts_download_button)
        speech_form.addRow(self.stt_enabled)
        self._add_row(speech_form, "whisper_model", self.stt_model)
        speech_form.addRow(self.whisper_status)
        speech_form.addRow(self.whisper_progress)
        speech_form.addRow(self.whisper_download_button)
        self._add_row(speech_form, "stt_device", self.stt_device)
        layout.addWidget(self.speech_group)

        self.behavior_group = QGroupBox()
        behavior_form = QFormLayout(self.behavior_group)
        self.screen_index = self._spinbox(0, 32)
        self.portrait_ratio = QDoubleSpinBox()
        self.portrait_ratio.setRange(0.2, 1.0)
        self.portrait_ratio.setSingleStep(0.05)
        self.portrait_ratio.setDecimals(2)
        self.thinking_minutes = self._spinbox(1, 1_440)
        self.away_minutes = self._spinbox(2, 1_440)
        self.history_limit = self._spinbox(4, 200)
        self._add_row(behavior_form, "screen_index", self.screen_index)
        self._add_row(
            behavior_form,
            "portrait_ratio",
            self.portrait_ratio,
        )
        self._add_row(
            behavior_form,
            "thinking_reminder",
            self.thinking_minutes,
        )
        self._add_row(behavior_form, "away_reminder", self.away_minutes)
        self._add_row(
            behavior_form,
            "conversation_memory",
            self.history_limit,
        )
        layout.addWidget(self.behavior_group)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    @staticmethod
    def _editable_combo() -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        return combo

    @staticmethod
    def _path_picker(field: QLineEdit, button: QPushButton) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field, 1)
        layout.addWidget(button)
        return container

    @staticmethod
    def _password_field() -> QLineEdit:
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        return field

    @staticmethod
    def _spinbox(minimum: int, maximum: int) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        return spinbox

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_combo_item_text(
        combo: QComboBox,
        data: str,
        text: str,
    ) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setItemText(index, text)

    @staticmethod
    def _set_editable_combo(combo: QComboBox, value: str) -> None:
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def _load_values(self, settings: AppSettings) -> None:
        self._set_combo_data(self.language_combo, settings.ui_language)
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
        self.deepseek_thinking.setChecked(settings.api.deepseek_thinking)
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
        self.tts_engine_root.setText(settings.tts.engine_root)
        self.tts_model_dir.setText(settings.tts.model_dir)
        self.stt_enabled.setChecked(settings.stt.enabled)
        self._set_editable_combo(self.stt_model, settings.stt.model)
        self.stt_device.setCurrentText(settings.stt.device)
        self.screen_index.setValue(settings.display.screen_index)
        self.portrait_ratio.setValue(
            settings.display.portrait_screen_ratio
        )
        self.thinking_minutes.setValue(settings.idle.thinking_minutes)
        self.away_minutes.setValue(settings.idle.away_minutes)
        self.history_limit.setValue(settings.history_limit)

    def _language(self) -> str:
        language = self.language_combo.currentData()
        return language if language in TRANSLATIONS else "en"

    def _text(self, key: str, **values: object) -> str:
        text = TRANSLATIONS[self._language()][key]
        return text.format(**values) if values else text

    def _on_language_changed(self) -> None:
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        title_key = "title_setup" if self._first_run else "title_settings"
        self.setWindowTitle(self._text(title_key))
        self.intro_label.setText(self._text("intro"))
        self.language_label.setText(self._text("language"))
        self.tabs.setTabText(0, self._text("tab_models"))
        self.tabs.setTabText(1, self._text("tab_character"))
        self.tabs.setTabText(2, self._text("tab_automation"))

        self.backend_group.setTitle(self._text("backend_group"))
        self.ollama_group.setTitle(self._text("ollama_group"))
        self.api_group.setTitle(self._text("api_group"))
        self.identity_group.setTitle(self._text("identity_group"))
        self.prompt_group.setTitle(self._text("prompt_group"))
        self.vision_group.setTitle(self._text("vision_group"))
        self.speech_group.setTitle(self._text("speech_group"))
        self.behavior_group.setTitle(self._text("behavior_group"))

        for key, labels in self._form_labels.items():
            for label in labels:
                label.setText(self._text(key))

        self._set_combo_item_text(
            self.mode_combo,
            "ollama",
            self._text("mode_ollama"),
        )
        self._set_combo_item_text(
            self.mode_combo,
            "api",
            self._text("mode_api"),
        )
        self._set_combo_item_text(
            self.api_provider,
            "aliyun",
            self._text("provider_aliyun"),
        )
        self._set_combo_item_text(
            self.portrait,
            "a",
            self._text("portrait_a"),
        )
        self._set_combo_item_text(
            self.portrait,
            "b",
            self._text("portrait_b"),
        )

        self.deepseek_thinking.setText(self._text("deepseek_thinking"))
        self.deepseek_note.setText(self._text("deepseek_note"))
        self.fetch_models_button.setText(self._text("load_models"))
        self.model_list_help.setText(self._text("model_list_help"))
        self.prompt_help.setText(self._text("prompt_help"))
        self.personality_prompt.setPlaceholderText(
            self._text("prompt_placeholder")
        )
        self.import_button.setText(self._text("import_prompt"))
        self.vision_enabled.setText(self._text("vision_enabled"))
        self.tts_enabled.setText(self._text("tts_enabled"))
        self.tts_engine_browse.setText(self._text("browse"))
        self.tts_model_browse.setText(self._text("browse"))
        self.tts_download_button.setText(self._text("tts_download"))
        self._render_tts_service_button()
        self.stt_enabled.setText(self._text("stt_enabled"))
        self.whisper_download_button.setText(
            self._text("whisper_download")
        )
        self.deepseek_key.setPlaceholderText(
            self._text("password_placeholder")
        )
        self.aliyun_key.setPlaceholderText(
            self._text("password_placeholder")
        )

        seconds = self._text("seconds")
        for spinbox in (
            self.ollama_timeout,
            self.api_timeout,
            self.vision_interval,
            self.tts_timeout,
        ):
            spinbox.setSuffix(seconds)
        minutes = self._text("minutes")
        self.thinking_minutes.setSuffix(minutes)
        self.away_minutes.setSuffix(minutes)
        self.history_limit.setSuffix(self._text("messages"))

        save_button = self.buttons.button(QDialogButtonBox.Save)
        cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        if save_button is not None:
            save_button.setText(self._text("save"))
        if cancel_button is not None:
            cancel_button.setText(self._text("cancel"))

        self._update_vision_compatibility()
        self._render_status()
        self._render_whisper_status()
        self._render_tts_status()

    def _set_status(self, key: str | None, **values: object) -> None:
        self._status_key = key
        self._status_values = values
        self._render_status()

    def _render_status(self) -> None:
        if self._status_key is None:
            self.status_label.clear()
            return
        self.status_label.setText(
            self._text(self._status_key, **self._status_values)
        )

    def _set_whisper_status(
        self,
        key: str,
        **values: object,
    ) -> None:
        self._whisper_status_key = key
        self._whisper_status_values = values
        self._render_whisper_status()

    def _render_whisper_status(self) -> None:
        if not hasattr(self, "whisper_status"):
            return
        self.whisper_status.setText(
            self._text(
                self._whisper_status_key,
                **self._whisper_status_values,
            )
        )

    def _set_tts_status(self, key: str, **values: object) -> None:
        self._tts_status_key = key
        self._tts_status_values = values
        self._render_tts_status()

    def _render_tts_status(self) -> None:
        if not hasattr(self, "tts_status"):
            return
        self.tts_status.setText(
            self._text(self._tts_status_key, **self._tts_status_values)
        )

    def _update_whisper_state(self) -> None:
        if not hasattr(self, "whisper_download_button"):
            return
        enabled = self.stt_enabled.isChecked()
        model_name = self.stt_model.currentText().strip()
        repository = model_repository(model_name) if model_name else ""
        snapshot = self.download_manager.snapshot(
            whisper_job_id(repository)
        )
        downloading = snapshot.status in {
            "preparing",
            "checking",
            "downloading",
        }
        self.stt_model.setEnabled(enabled and not downloading)
        self.stt_device.setEnabled(enabled)
        self.whisper_download_button.setEnabled(False)
        self._render_progress(self.whisper_progress, snapshot)
        if not enabled:
            self._pending_whisper_model = None
            self._set_whisper_status("whisper_disabled")
            return
        if not model_name:
            self._set_whisper_status("whisper_missing")
            return
        if downloading:
            return
        if (
            self._whisper_check_worker is not None
            and self._whisper_check_worker.isRunning()
        ):
            self._pending_whisper_model = model_name
            self._set_whisper_status("whisper_checking")
            return
        self._start_whisper_check(model_name)

    def _start_whisper_check(self, model_name: str) -> None:
        self._set_whisper_status("whisper_checking")
        worker = WhisperModelCheckWorker(model_name, self)
        self._whisper_check_worker = worker
        worker.checked.connect(self._on_whisper_checked)
        worker.finished.connect(
            lambda: self._finish_whisper_check(worker)
        )
        worker.start()

    def _on_whisper_checked(self, model_name: str, path: str) -> None:
        if (
            not self.stt_enabled.isChecked()
            or model_name != self.stt_model.currentText().strip()
        ):
            return
        if path:
            self.whisper_progress.hide()
            self.whisper_download_button.setEnabled(False)
            self._set_whisper_status("whisper_installed", path=path)
        else:
            repository = model_repository(model_name)
            snapshot = self.download_manager.snapshot(
                whisper_job_id(repository)
            )
            if snapshot.status in {
                "preparing",
                "checking",
                "downloading",
            }:
                self._render_whisper_download(model_name, snapshot)
            elif snapshot.status == "failed":
                self.whisper_download_button.setEnabled(True)
                self._set_whisper_status(
                    "whisper_download_failed",
                    message=snapshot.message,
                )
            else:
                self.whisper_download_button.setEnabled(True)
                self._set_whisper_status("whisper_missing")

    def _finish_whisper_check(
        self,
        worker: WhisperModelCheckWorker,
    ) -> None:
        if self._whisper_check_worker is worker:
            self._whisper_check_worker = None
        worker.deleteLater()
        pending = self._pending_whisper_model
        self._pending_whisper_model = None
        current = self.stt_model.currentText().strip()
        if (
            self.stt_enabled.isChecked()
            and pending
            and pending == current
        ):
            self._start_whisper_check(pending)

    def _download_whisper_model(self) -> None:
        model_name = self.stt_model.currentText().strip()
        if not self.stt_enabled.isChecked() or not model_name:
            return

        job_id = self.download_manager.start_whisper(model_name)
        snapshot = self.download_manager.snapshot(job_id)
        self.whisper_download_button.setEnabled(False)
        self.stt_model.setEnabled(False)
        self._render_whisper_download(model_name, snapshot)

    def _render_whisper_download(
        self,
        model_name: str,
        snapshot: DownloadSnapshot,
    ) -> None:
        self._render_progress(self.whisper_progress, snapshot)
        detail = self._download_detail(snapshot)
        if snapshot.status == "preparing":
            self._set_whisper_status(
                "whisper_preparing",
                model=model_name,
                detail=detail,
            )
            return
        if snapshot.status == "checking":
            self._set_whisper_status(
                "whisper_verifying",
                model=model_name,
                detail=detail,
            )
            return
        self._set_whisper_status(
            "whisper_downloading",
            model=model_name,
            detail=detail,
        )

    def _update_tts_state(self) -> None:
        if not hasattr(self, "tts_status"):
            return
        enabled = self.tts_enabled.isChecked()
        local_endpoint = is_loopback_url(self.tts_url.text().strip())
        self.tts_engine_root.setEnabled(enabled and local_endpoint)
        self.tts_engine_browse.setEnabled(enabled and local_endpoint)
        self.tts_model_dir.setEnabled(enabled and local_endpoint)
        self.tts_model_browse.setEnabled(enabled and local_endpoint)
        self.tts_download_button.setEnabled(False)
        self.tts_service_button.setVisible(local_endpoint)
        self._set_tts_service_button("start", False)
        if (
            self._tts_service_worker is not None
            and self._tts_service_worker.isRunning()
        ):
            return
        snapshot = self.download_manager.snapshot(TTS_JOB_ID)
        if snapshot.status in {
            "preparing",
            "checking",
            "downloading",
            "extracting",
            "installing",
            "cleaning",
        }:
            self._render_tts_download(snapshot)
            return
        self.tts_progress.hide()
        self.tts_extract_progress.hide()
        if not enabled:
            self._set_tts_status("tts_disabled")
            return
        if (
            self._tts_check_worker is not None
            and self._tts_check_worker.isRunning()
        ):
            self._pending_tts_check = True
            self._set_tts_status("tts_checking")
            return
        try:
            settings = TTSSettings(
                enabled=True,
                base_url=self.tts_url.text().strip(),
                remote_reference_root=(
                    self.tts_reference_root.text().strip()
                ),
                engine_root=self.tts_engine_root.text().strip(),
                model_dir=self.tts_model_dir.text().strip(),
                timeout_seconds=self.tts_timeout.value(),
            )
        except ValidationError:
            self._set_tts_status("tts_invalid")
            return
        self._set_tts_status("tts_checking")
        worker = TTSCheckWorker(settings, self)
        self._tts_check_worker = worker
        worker.checked.connect(self._on_tts_checked)
        worker.finished.connect(lambda: self._finish_tts_check(worker))
        worker.start()

    def _on_tts_checked(
        self,
        state: TTSAssetState,
        reachable: bool,
    ) -> None:
        if not self.tts_enabled.isChecked():
            return
        local_endpoint = is_loopback_url(self.tts_url.text().strip())
        if not local_endpoint:
            key = "tts_external_online" if reachable else "tts_external_offline"
            self._set_tts_status(key)
            return

        configured_engine = self.tts_engine_root.text().strip()
        if state.engine_root is not None and (
            not configured_engine
            or not (
                Path(configured_engine).expanduser() / "api_v2.py"
            ).is_file()
        ):
            self.tts_engine_root.setText(str(state.engine_root))
        if (
            state.model_directory is not None
            and (
                not self.tts_model_dir.text().strip()
                or not Path(
                    self.tts_model_dir.text().strip()
                ).expanduser().is_dir()
            )
        ):
            self.tts_model_dir.setText(str(state.model_directory))

        self._tts_engine_download_needed = (
            not reachable and not state.engine_ready
        )
        if reachable:
            if get_tts_service_manager().owns_running_process():
                self._set_tts_service_button("stop", True)
            else:
                self._set_tts_service_button("online", False)
        else:
            can_start = (
                state.engine_ready
                and state.model_ready
                and state.reference_voices_ready
            )
            self._set_tts_service_button("start", can_start)
        if not state.reference_voices_ready:
            self._set_tts_status("tts_references_missing")
            self.tts_download_button.setEnabled(True)
            if not self._tts_download_prompted:
                self._tts_download_prompted = True
                self._request_tts_download()
            return
        if state.model_ready:
            if reachable:
                self.tts_download_button.setEnabled(False)
                self._set_tts_status("tts_ready_online")
            elif state.engine_root is None:
                self.tts_download_button.setEnabled(True)
                self._set_tts_status("tts_engine_missing")
            elif not state.engine_ready:
                self.tts_download_button.setEnabled(True)
                self._set_tts_status("tts_engine_incomplete")
            else:
                self.tts_download_button.setEnabled(False)
                self._set_tts_status("tts_ready_offline")
            if (
                self._tts_engine_download_needed
                and not self._tts_download_prompted
            ):
                self._tts_download_prompted = True
                self._request_tts_download()
            return

        self._set_tts_status("tts_model_missing")
        self.tts_download_button.setEnabled(True)
        if self._tts_download_prompted:
            return
        self._tts_download_prompted = True
        self._request_tts_download()

    def _set_tts_service_button(
        self,
        mode: str,
        enabled: bool,
    ) -> None:
        self._tts_service_button_mode = mode
        self.tts_service_button.setEnabled(enabled)
        self._render_tts_service_button()

    def _render_tts_service_button(self) -> None:
        if not hasattr(self, "tts_service_button"):
            return
        key = {
            "start": "tts_service_start",
            "stop": "tts_service_stop",
            "online": "tts_service_online",
        }.get(self._tts_service_button_mode, "tts_service_start")
        self.tts_service_button.setText(self._text(key))

    def _toggle_tts_service(self) -> None:
        if (
            self._tts_service_worker is not None
            and self._tts_service_worker.isRunning()
        ):
            return
        try:
            settings = TTSSettings(
                enabled=True,
                base_url=self.tts_url.text().strip(),
                remote_reference_root=self.tts_reference_root.text().strip(),
                engine_root=self.tts_engine_root.text().strip(),
                model_dir=self.tts_model_dir.text().strip(),
                timeout_seconds=self.tts_timeout.value(),
            )
        except ValidationError:
            self._set_tts_status("tts_invalid")
            return

        action = (
            "stop"
            if get_tts_service_manager().owns_running_process()
            else "start"
        )
        self._tts_service_error = None
        self.tts_service_button.setEnabled(False)
        self._set_tts_status(
            "tts_service_stopping"
            if action == "stop"
            else "tts_service_locating"
        )
        worker = TTSServiceWorker(settings, action, self)
        self._tts_service_worker = worker
        worker.stage_changed.connect(self._on_tts_service_stage)
        worker.succeeded.connect(self._on_tts_service_succeeded)
        worker.failed.connect(self._on_tts_service_failed)
        worker.finished.connect(
            lambda: self._finish_tts_service_worker(worker)
        )
        worker.start()

    def _on_tts_service_stage(self, stage: str) -> None:
        key = {
            "locating_engine": "tts_service_locating",
            "starting_process": "tts_service_starting",
            "waiting_for_api": "tts_service_waiting",
            "waiting_for_existing_start": "tts_service_waiting_existing",
            "loading_weights": "tts_service_loading_weights",
        }.get(stage)
        if key is not None:
            self._set_tts_status(key)

    def _on_tts_service_succeeded(self, action: str) -> None:
        self._set_tts_status(
            "tts_service_stopped"
            if action == "stopped"
            else "tts_service_started"
        )

    def _on_tts_service_failed(self, message: str) -> None:
        self._tts_service_error = message
        self._set_tts_status("tts_service_failed", message=message)

    def _finish_tts_service_worker(
        self,
        worker: TTSServiceWorker,
    ) -> None:
        if self._tts_service_worker is worker:
            self._tts_service_worker = None
        worker.deleteLater()
        if self._tts_service_error is None:
            self._update_tts_state()
        else:
            self.tts_service_button.setEnabled(True)

    def _request_tts_download(self) -> None:
        if not self.tts_enabled.isChecked():
            return
        answer = QMessageBox.question(
            self,
            self._text("tts_download_consent_title"),
            self._text(
                "tts_download_consent_body_with_engine"
                if self._tts_engine_download_needed
                else "tts_download_consent_body"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        destination = managed_tts_model_dir()
        self.tts_model_dir.setText(str(destination))
        self.download_manager.start_tts(
            include_engine=self._tts_engine_download_needed,
        )
        self.tts_download_button.setEnabled(False)
        self._render_tts_download(
            self.download_manager.snapshot(TTS_JOB_ID)
        )

    def _finish_tts_check(self, worker: TTSCheckWorker) -> None:
        if self._tts_check_worker is worker:
            self._tts_check_worker = None
        worker.deleteLater()
        if self._pending_tts_check:
            self._pending_tts_check = False
            self._update_tts_state()

    def _render_tts_download(self, snapshot: DownloadSnapshot) -> None:
        if snapshot.status == "extracting":
            self.tts_progress.hide()
            self._render_progress(
                self.tts_extract_progress,
                snapshot,
            )
            self._set_tts_status(
                "tts_extracting",
                detail=self._extraction_detail(snapshot),
            )
            return
        if snapshot.status in {"installing", "cleaning"}:
            self.tts_progress.hide()
            self._render_progress(
                self.tts_extract_progress,
                snapshot,
            )
            key = (
                "tts_installing"
                if snapshot.status == "installing"
                else "tts_cleaning"
            )
            self._set_tts_status(
                key,
                detail=self._installation_detail(snapshot),
            )
            return
        self.tts_extract_progress.hide()
        self._render_progress(self.tts_progress, snapshot)
        if snapshot.status == "preparing":
            self._set_tts_status(
                "tts_preparing",
                detail=self._download_detail(snapshot),
            )
            return
        if snapshot.status == "checking":
            self._set_tts_status(
                "tts_checking_files",
                detail=self._download_detail(snapshot),
            )
            return
        self._set_tts_status(
            "tts_downloading",
            detail=self._download_detail(snapshot),
        )

    def _on_download_changed(
        self,
        job_id: str,
        snapshot: DownloadSnapshot,
    ) -> None:
        if job_id == TTS_JOB_ID:
            if snapshot.status in {
                "preparing",
                "checking",
                "downloading",
                "extracting",
                "installing",
                "cleaning",
            }:
                self._render_tts_download(snapshot)
            elif snapshot.status == "completed":
                self.tts_download_button.setEnabled(False)
                self.tts_model_dir.setText(snapshot.destination)
                self._render_progress(self.tts_progress, snapshot)
                self.tts_extract_progress.hide()
                self._set_tts_status(
                    "tts_downloaded",
                    path=snapshot.destination,
                )
                self._update_tts_state()
            elif snapshot.status == "failed":
                self.tts_download_button.setEnabled(
                    self.tts_enabled.isChecked()
                    and is_loopback_url(self.tts_url.text().strip())
                )
                self._render_progress(self.tts_progress, snapshot)
                self.tts_extract_progress.hide()
                self._set_tts_status(
                    "tts_download_failed",
                    message=snapshot.message,
                )
            return

        model_name = self.stt_model.currentText().strip()
        if not model_name:
            return
        expected = whisper_job_id(model_repository(model_name))
        if job_id != expected:
            return
        if snapshot.status in {
            "preparing",
            "checking",
            "downloading",
        }:
            self._render_whisper_download(model_name, snapshot)
        elif snapshot.status == "completed":
            self.stt_model.setEnabled(self.stt_enabled.isChecked())
            self._render_progress(self.whisper_progress, snapshot)
            self._set_whisper_status(
                "whisper_downloaded",
                path=snapshot.destination,
            )
        elif snapshot.status == "failed":
            self.stt_model.setEnabled(self.stt_enabled.isChecked())
            self.whisper_download_button.setEnabled(
                self.stt_enabled.isChecked()
            )
            self._render_progress(self.whisper_progress, snapshot)
            self._set_whisper_status(
                "whisper_download_failed",
                message=snapshot.message,
            )

    @staticmethod
    def _render_progress(
        progress: QProgressBar,
        snapshot: DownloadSnapshot,
    ) -> None:
        active = snapshot.status in {
            "preparing",
            "checking",
            "downloading",
            "extracting",
            "installing",
            "cleaning",
        }
        should_show = active or snapshot.status == "failed"
        progress.setVisible(should_show)
        if not should_show:
            return
        if snapshot.total <= 0:
            progress.setRange(0, 0)
            return
        progress.setRange(0, 1_000)
        value = min(1_000, int(snapshot.received / snapshot.total * 1_000))
        progress.setValue(value)

    def _download_detail(self, snapshot: DownloadSnapshot) -> str:
        if snapshot.total <= 0:
            return self._text("download_preparing")
        percent = snapshot.received / snapshot.total * 100
        detail = (
            f"{percent:.1f}% · {self._format_bytes(snapshot.received)} / "
            f"{self._format_bytes(snapshot.total)}"
        )
        if snapshot.current_file:
            detail += f" · {Path(snapshot.current_file).name}"
        return detail

    def _extraction_detail(self, snapshot: DownloadSnapshot) -> str:
        if snapshot.total <= 0:
            return "preparing"
        percent = snapshot.received / snapshot.total * 100
        detail = (
            f"{percent:.1f}% · {snapshot.received} / "
            f"{snapshot.total} {self._text('download_files')}"
        )
        if snapshot.current_file:
            detail += f" · {Path(snapshot.current_file).name}"
        return detail

    def _installation_detail(self, snapshot: DownloadSnapshot) -> str:
        if snapshot.total <= 0:
            return (
                Path(snapshot.current_file).name
                if snapshot.current_file
                else self._text("download_preparing")
            )
        percent = snapshot.received / snapshot.total * 100
        detail = (
            f"{percent:.1f}% · {snapshot.received} / "
            f"{snapshot.total} {self._text('download_steps')}"
        )
        if snapshot.current_file:
            detail += f" · {Path(snapshot.current_file).name}"
        return detail

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _browse_tts_engine(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._text("tts_engine_root"),
            self.tts_engine_root.text().strip() or str(Path.home()),
        )
        if selected:
            self.tts_engine_root.setText(selected)
            self._update_tts_state()

    def _browse_tts_model(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._text("tts_model_dir"),
            self.tts_model_dir.text().strip() or str(Path.home()),
        )
        if selected:
            self.tts_model_dir.setText(selected)
            self._update_tts_state()

    def _update_backend_visibility(self) -> None:
        if not hasattr(self, "backend_stack"):
            return
        mode = self.mode_combo.currentData()
        self.backend_stack.setCurrentIndex(0 if mode == "ollama" else 1)
        self._update_vision_compatibility()

    def _update_api_provider(self) -> None:
        if not hasattr(self, "api_provider_stack"):
            return
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
        key = "vision_unsupported" if unsupported else "vision_supported"
        self.vision_compatibility.setText(self._text(key))

    def _import_prompt(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            self._text("import_title"),
            str(Path.home()),
            self._text("text_filter"),
        )
        if not file_name:
            return
        try:
            self.personality_prompt.setPlainText(
                Path(file_name).read_text(encoding="utf-8")
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                self._text("import_failed"),
                str(exc),
            )

    def _form_settings(self) -> AppSettings:
        personality_path = get_user_data_dir() / "personality.txt"
        return AppSettings(
            ui_language=self._language(),
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
                deepseek_thinking=self.deepseek_thinking.isChecked(),
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
                engine_root=self.tts_engine_root.text().strip(),
                model_dir=self.tts_model_dir.text().strip(),
                timeout_seconds=self.tts_timeout.value(),
            ),
            stt=STTSettings(
                enabled=self.stt_enabled.isChecked(),
                model=self.stt_model.currentText().strip(),
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
            QMessageBox.warning(
                self,
                self._text("invalid_settings"),
                str(exc),
            )
            return

        self.fetch_models_button.setEnabled(False)
        self._set_status("connecting")
        self._model_target = (settings.mode, settings.api.provider)
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
            self._set_status("models_empty")
            return

        mode, provider = self._model_target or (
            self.mode_combo.currentData(),
            self.api_provider.currentData(),
        )
        targets: list[QComboBox]
        if mode == "ollama":
            targets = [self.ollama_chat_model, self.ollama_vision_model]
        elif provider == "aliyun":
            targets = [self.aliyun_chat_model, self.aliyun_vision_model]
        else:
            targets = [self.deepseek_chat_model]

        unique_models = list(dict.fromkeys(models))
        for combo in targets:
            selected = combo.currentText().strip()
            choices = list(unique_models)
            if selected and selected not in choices:
                choices.insert(0, selected)
            combo.clear()
            combo.addItems(choices)
            if selected:
                combo.setCurrentText(selected)
        self._set_status("models_found", count=len(unique_models))

    def _on_models_error(self, message: str) -> None:
        self._set_status("connection_failed", message=message)

    def _show_running_message(self) -> None:
        QMessageBox.information(
            self,
            self._text("test_running_title"),
            self._text("test_running_body"),
        )

    def accept(self) -> None:
        if self._background_check_is_running():
            self._show_running_message()
            return
        prompt = self.personality_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(
                self,
                self._text("missing_personality"),
                self._text("missing_personality_body"),
            )
            return
        try:
            settings = self._form_settings()
        except ValidationError as exc:
            QMessageBox.warning(
                self,
                self._text("invalid_settings"),
                str(exc),
            )
            return
        if settings.requires_api_key():
            QMessageBox.warning(
                self,
                self._text("missing_key"),
                self._text("missing_key_body"),
            )
            return

        personality_path = settings.personality_path()
        try:
            personality_path.parent.mkdir(parents=True, exist_ok=True)
            personality_path.write_text(prompt + "\n", encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self,
                self._text("save_failed"),
                str(exc),
            )
            return

        self._result = settings
        super().accept()

    def reject(self) -> None:
        if self._background_check_is_running():
            self._show_running_message()
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._background_check_is_running():
            event.ignore()
            self._show_running_message()
            return
        super().closeEvent(event)

    def _background_check_is_running(self) -> bool:
        return bool(
            (
                self._model_worker is not None
                and self._model_worker.isRunning()
            )
            or (
                self._whisper_check_worker is not None
                and self._whisper_check_worker.isRunning()
            )
            or (
                self._tts_check_worker is not None
                and self._tts_check_worker.isRunning()
            )
            or (
                self._tts_service_worker is not None
                and self._tts_service_worker.isRunning()
            )
        )

    def result_settings(self) -> AppSettings:
        if self._result is None:
            return self._original.model_copy(deep=True)
        return self._result.model_copy(deep=True)
