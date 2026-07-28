"""Shared Qt settings dialog."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
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
    QLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from aipet.core.download_manager import (
    TTS_JOB_ID,
    DownloadManager,
    DownloadSnapshot,
    whisper_job_id,
)
from aipet.core.audio_devices import (
    decode_audio_input_device,
    refresh_audio_input_devices,
)
from aipet.core.backends import create_backend, create_vision_backend
from aipet.core.cache import clear_runtime_cache
from aipet.core.config import (
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
from aipet.core.runtime_logging import get_logger
from aipet.core.tts_assets import (
    TTSAssetState,
    configure_local_tts_weights,
    locate_tts_assets,
    tts_service_is_reachable,
)
from aipet.core.tts_service import (
    TTSServiceError,
    get_tts_service_manager,
)
from aipet.core.whisper_models import (
    WHISPER_MODELS,
    find_local_model,
    looks_like_local_model_path,
    model_repository,
)
from aipet.platforms import (
    CredentialError,
    PlatformRuntime,
    get_platform_runtime,
)


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "title_setup": "AIpet Initial Setup",
        "title_settings": "AIpet Settings",
        "language": "Language / 语言",
        "tab_models": "Language models",
        "tab_extensions": "Extensions",
        "tab_character": "Character",
        "tab_automation": "Automation",
        "tab_display": "Display",
        "tab_other": "Other",
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
        "provider_openai": "OpenAI",
        "deepseek_api_key": "API key / DEEPSEEK_API_KEY",
        "aliyun_api_key": "API key / DASHSCOPE_API_KEY",
        "openai_api_key": "API key / OPENAI_API_KEY",
        "base_url": "Base URL",
        "deepseek_thinking": "Enable DeepSeek thinking mode (slower)",
        "deepseek_note": (
            "DeepSeek V4 is used for chat. Choose the independent vision "
            "backend under Extensions."
        ),
        "load_models": "Test connection & load models",
        "model_list_help": (
            "Uses Ollama /api/tags or the provider's /models endpoint. "
            "Model fields stay editable for custom or unlisted IDs."
        ),
        "load_vision_models": "Test connection & load vision models",
        "vision_model_list_help": (
            "Loads the complete model list from the vision provider and "
            "keeps the field editable for custom model IDs."
        ),
        "identity_group": "Identity",
        "user_name": "User name",
        "portrait_set": "Default portrait set",
        "portrait_a": "Portrait A",
        "portrait_b": "Portrait B",
        "outfit": "Default outfit",
        "outfit_sleepwear": "Sleepwear",
        "outfit_casual": "Casual outfit",
        "outfit_uniform": "School uniform",
        "outfit_kimono": "Purple kimono",
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
        "vision_provider": "Vision backend",
        "vision_provider_ollama": "Ollama (local service)",
        "vision_provider_aliyun": "Alibaba Cloud Model Studio",
        "vision_provider_openai": "OpenAI",
        "vision_enabled": (
            "Check the selected screen and react only to significant changes"
        ),
        "interval": "Interval",
        "vision_supported": (
            "The first screenshot establishes a baseline. Near-identical "
            "screens stay local; automatic reactions share a 3-minute cooldown. "
            "The vision backend is independent from the chat backend."
        ),
        "tts_group": "Text-to-speech (GPT-SoVITS)",
        "whisper_group": "Speech input (Whisper)",
        "tts_enabled": "Use GPT-SoVITS-compatible TTS",
        "tts_backend": "TTS location",
        "tts_backend_local": "Local computer",
        "tts_backend_autodl": "AutoDL cloud",
        "tts_endpoint": "TTS endpoint",
        "tts_timeout": "TTS timeout",
        "tts_engine_root": "GPT-SoVITS download/install directory",
        "tts_model_dir": "Voice model download directory (includes references)",
        "tts_autodl_ssh_command": "AutoDL SSH login command",
        "tts_autodl_password": "AutoDL SSH password",
        "tts_autodl_remote_command": "Remote TTS start command",
        "tts_autodl_reference_root": "Remote reference voice directory",
        "tts_autodl_password_placeholder": (
            "Leave blank to keep the password saved by the operating system"
        ),
        "browse": "Browse…",
        "tts_disabled": (
            "Enable TTS to check the engine, voice model, references, and service."
        ),
        "tts_invalid": "Enter a valid TTS endpoint before checking it.",
        "tts_autodl_missing": (
            "Enter the AutoDL SSH login command, password, remote start "
            "command, and remote reference voice directory."
        ),
        "tts_password_store_failed": (
            "The operating system could not save the AutoDL password "
            "securely: {message}"
        ),
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
        "tts_service_connecting_ssh": "Connecting to AutoDL over SSH…",
        "tts_service_starting_remote": "Running the AutoDL TTS start command…",
        "tts_service_starting_tunnel": "Opening the local SSH tunnel…",
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
        "whisper_model": "Whisper model or repository ID",
        "whisper_model_dir": "Whisper model download directory",
        "stt_input_device": "Recording device",
        "stt_input_default": "System default ({device})",
        "stt_input_default_unknown": "System default input",
        "stt_input_unavailable": "Unavailable: {device}",
        "stt_device": "STT device",
        "stt_device_auto": "Auto",
        "stt_device_cuda": (
            "CUDA (requires the AIpet-with-cuda build; unavailable otherwise)"
        ),
        "stt_device_cpu": "CPU",
        "whisper_download": "Download model",
        "whisper_disabled": (
            "Enable speech input to check the selected download directory."
        ),
        "whisper_checking": "Checking the selected model directory…",
        "whisper_installed": "Available locally: {path}",
        "whisper_missing": (
            "The selected model is not available in the download directory. "
            "Choose a directory, then download the model."
        ),
        "whisper_path_missing": (
            "The entered local model directory is incomplete or does not exist."
        ),
        "whisper_downloading": (
            "Downloading {model}: {detail}"
        ),
        "whisper_preparing": "Preparing {model}: {detail}",
        "whisper_verifying": "Checking {model}: {detail}",
        "whisper_downloaded": "Download complete. Available locally: {path}",
        "whisper_download_failed": "Download failed: {message}",
        "download_path_required_title": "Download directory required",
        "tts_model_path_required": (
            "Select the voice model download directory before downloading."
        ),
        "tts_engine_path_required": (
            "Select the GPT-SoVITS download/install directory before "
            "downloading the engine."
        ),
        "whisper_path_required": (
            "Select the Whisper model download directory before downloading."
        ),
        "download_path_invalid": "The selected directory cannot be used: {message}",
        "automation_group": "Idle behavior and memory",
        "settings_help": "Explain these settings",
        "automation_help_title": "Idle behavior and memory",
        "automation_help_body": (
            "Thinking reminder: after this much inactivity, the character may "
            "gently check whether you are still there. It triggers at most "
            "once per idle period.\n\n"
            "Away reminder: after the longer inactivity threshold, the "
            "character treats you as away. When you return, she may welcome "
            "you back. This value must be greater than the thinking reminder."
            "\n\n"
            "Conversation memory: the maximum number of recent messages kept "
            "and supplied as conversation context.\n\n"
            "Do not disturb: disables proactive idle and return messages; "
            "manual conversation still works."
        ),
        "do_not_disturb": "Do not disturb",
        "clear_history": "Clear conversation history…",
        "clear_history_confirm_title": "Clear conversation history?",
        "clear_history_confirm_body": (
            "This immediately removes all saved conversation history. "
            "The action cannot be undone by cancelling this settings window."
        ),
        "history_cleared": "Conversation history has been cleared.",
        "history_unavailable_first_run": (
            "Conversation history is not available during initial setup."
        ),
        "data_group": "Data management",
        "conversation_history_data": "Conversation history",
        "runtime_cache_data": "Temporary screenshots, speech, and recordings",
        "clear_cache": "Clear cache…",
        "clear_cache_confirm_title": "Clear cached files?",
        "clear_cache_confirm_body": (
            "This removes temporary screenshots, generated speech, and "
            "recordings. Settings, conversation history, models, and logs "
            "are not affected."
        ),
        "cache_cleared": "Cleared {files} cached files, freeing {size}.",
        "cache_empty": "The cache is already empty.",
        "cache_clear_partial": (
            "Cleared {files} cached files ({size}), but {failed} files or "
            "folders are still in use or could not be removed."
        ),
        "display_group": "Screen and portrait",
        "display_help_title": "Screen and portrait",
        "display_help_body": (
            "Screen index: the zero-based position in the current screen "
            "list. If the index is unavailable, the primary screen is used."
            "\n\n"
            "Portrait height ratio: the character's target height as a share "
            "of the selected screen's available height.\n\n"
            "Live diagnostic console: opens a live log window for diagnosing "
            "model, TTS, recording, and other runtime problems."
        ),
        "screen_index": "Screen index",
        "portrait_ratio": "Portrait height ratio",
        "show_log_console": "Open live diagnostic console",
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
        "language": "界面语言 / Language",
        "tab_models": "语言模型",
        "tab_extensions": "拓展功能",
        "tab_character": "角色",
        "tab_automation": "自动行为",
        "tab_display": "显示",
        "tab_other": "其他",
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
        "provider_openai": "OpenAI",
        "deepseek_api_key": "API Key / DEEPSEEK_API_KEY",
        "aliyun_api_key": "API Key / DASHSCOPE_API_KEY",
        "openai_api_key": "API Key / OPENAI_API_KEY",
        "base_url": "基础地址",
        "deepseek_thinking": "启用 DeepSeek 思考模式（响应更慢）",
        "deepseek_note": (
            "DeepSeek V4 用于对话；视觉后端请在“拓展功能”中独立选择。"
        ),
        "load_models": "测试连接并加载模型",
        "model_list_help": (
            "Ollama 使用 /api/tags，云端服务使用 /models。"
            "下拉框始终可以手动输入自定义或未列出的模型 ID。"
        ),
        "load_vision_models": "测试连接并加载视觉模型",
        "vision_model_list_help": (
            "从当前视觉服务地址读取完整模型列表；"
            "仍可手动输入自定义模型 ID。"
        ),
        "identity_group": "身份",
        "user_name": "用户名称",
        "portrait_set": "默认立绘组",
        "portrait_a": "立绘 A",
        "portrait_b": "立绘 B",
        "outfit": "默认服装",
        "outfit_sleepwear": "睡衣",
        "outfit_casual": "粉白便衣",
        "outfit_uniform": "校服",
        "outfit_kimono": "紫色和服",
        "prompt_group": "人格提示词",
        "prompt_help": (
            "这里仅描述人格。AIpet 会自动添加结构化 JSON 规则，"
            "请不要在这里重复编写输出格式。"
        ),
        "prompt_placeholder": "描述角色身份、说话风格、关系和行为边界……",
        "import_prompt": "从文本文件导入提示词…",
        "vision_group": "屏幕视觉",
        "vision_provider": "视觉后端",
        "vision_provider_ollama": "Ollama（本地服务）",
        "vision_provider_aliyun": "阿里云百炼",
        "vision_provider_openai": "OpenAI",
        "vision_enabled": "检查所选屏幕，仅在明显变化时主动回应",
        "interval": "间隔",
        "vision_supported": (
            "首次截图只建立基线；近似相同的画面不会送入视觉模型，"
            "所有自动主动回应共用 3 分钟冷却。"
            "视觉后端与语言模型后端相互独立。"
        ),
        "tts_group": "语音合成（GPT-SoVITS）",
        "whisper_group": "语音输入（Whisper）",
        "tts_enabled": "使用 GPT-SoVITS 兼容 TTS",
        "tts_backend": "TTS 位置",
        "tts_backend_local": "本机",
        "tts_backend_autodl": "AutoDL 云端",
        "tts_endpoint": "TTS 地址",
        "tts_timeout": "TTS 超时",
        "tts_engine_root": "GPT-SoVITS 下载及安装目录",
        "tts_model_dir": "角色语音模型下载目录（含参考音频）",
        "tts_autodl_ssh_command": "AutoDL SSH 登录命令",
        "tts_autodl_password": "AutoDL SSH 密码",
        "tts_autodl_remote_command": "远程 TTS 启动命令",
        "tts_autodl_reference_root": "服务器参考音频目录",
        "tts_autodl_password_placeholder": (
            "留空则继续使用操作系统安全保存的密码"
        ),
        "browse": "浏览…",
        "tts_disabled": "启用 TTS 后，将检查引擎、角色模型、参考音频和服务。",
        "tts_invalid": "请先填写有效的 TTS 地址。",
        "tts_autodl_missing": (
            "请填写 AutoDL SSH 登录命令、密码、远程启动命令和服务器参考音频目录。"
        ),
        "tts_password_store_failed": (
            "操作系统无法安全保存 AutoDL 密码：{message}"
        ),
        "tts_checking": "正在检查 GPT-SoVITS 组件……",
        "tts_ready_online": "角色语音模型完整，TTS 服务在线。",
        "tts_ready_offline": "角色语音模型完整，但 TTS 服务尚未运行。",
        "tts_service_start": "启动 TTS 服务",
        "tts_service_stop": "停止 TTS 服务",
        "tts_service_online": "TTS 服务在线",
        "tts_service_locating": "正在定位 GPT-SoVITS 运行环境……",
        "tts_service_starting": "正在启动 GPT-SoVITS 进程……",
        "tts_service_connecting_ssh": "正在通过 SSH 连接 AutoDL……",
        "tts_service_starting_remote": "正在执行 AutoDL TTS 启动命令……",
        "tts_service_starting_tunnel": "正在建立本机 SSH 隧道……",
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
        "whisper_model": "Whisper 模型或仓库 ID",
        "whisper_model_dir": "Whisper 模型下载目录",
        "stt_input_device": "录音设备",
        "stt_input_default": "系统默认（{device}）",
        "stt_input_default_unknown": "系统默认输入设备",
        "stt_input_unavailable": "当前不可用：{device}",
        "stt_device": "语音识别设备",
        "stt_device_auto": "自动",
        "stt_device_cuda": (
            "CUDA（请使用 AIpet-with-cuda 版本，否则无法使用）"
        ),
        "stt_device_cpu": "CPU",
        "whisper_download": "下载模型",
        "whisper_disabled": "启用语音输入后，将检查填写的模型下载目录。",
        "whisper_checking": "正在检查填写的模型目录……",
        "whisper_installed": "本地已安装：{path}",
        "whisper_missing": (
            "填写的下载目录中没有可用的所选模型。"
            "请选择目录，然后下载模型。"
        ),
        "whisper_path_missing": "填写的本地模型目录不存在或模型文件不完整。",
        "whisper_downloading": "正在下载 {model}：{detail}",
        "whisper_preparing": "正在准备 {model}：{detail}",
        "whisper_verifying": "正在校验 {model}：{detail}",
        "whisper_downloaded": "下载完成，本地路径：{path}",
        "whisper_download_failed": "下载失败：{message}",
        "download_path_required_title": "需要填写下载目录",
        "tts_model_path_required": "请先选择角色语音模型下载目录。",
        "tts_engine_path_required": "请先选择 GPT-SoVITS 下载及安装目录。",
        "whisper_path_required": "请先选择 Whisper 模型下载目录。",
        "download_path_invalid": "无法使用所选目录：{message}",
        "automation_group": "空闲行为与记忆",
        "settings_help": "解释这些设置",
        "automation_help_title": "空闲行为与记忆说明",
        "automation_help_body": (
            "思考提醒：持续无操作达到该时间后，角色可能会温和地询问你是否还在。"
            "每段空闲期间最多触发一次。\n\n"
            "离开提醒：持续无操作达到更长的时间后，角色会认为你暂时离开；"
            "检测到你回来后，可能会欢迎你。该时间必须大于思考提醒。\n\n"
            "对话记忆：最多保留并作为对话上下文发送的最近消息数量。\n\n"
            "勿扰模式：停止主动的空闲提醒和回来问候，但手动对话仍可正常使用。"
        ),
        "do_not_disturb": "勿扰模式",
        "clear_history": "清除历史对话…",
        "clear_history_confirm_title": "确定清除历史对话？",
        "clear_history_confirm_body": (
            "这会立即清除全部已保存的历史对话。"
            "即使之后取消设置，也无法撤销该操作。"
        ),
        "history_cleared": "历史对话已清除。",
        "history_unavailable_first_run": "首次设置时没有可清除的历史对话。",
        "data_group": "数据管理",
        "conversation_history_data": "历史对话",
        "runtime_cache_data": "临时截图、合成语音与录音",
        "clear_cache": "清除缓存…",
        "clear_cache_confirm_title": "确定清除缓存文件？",
        "clear_cache_confirm_body": (
            "这会删除临时截图、合成语音和录音。"
            "设置、历史对话、模型与日志不会受到影响。"
        ),
        "cache_cleared": "已清除 {files} 个缓存文件，释放 {size}。",
        "cache_empty": "缓存已经是空的。",
        "cache_clear_partial": (
            "已清除 {files} 个缓存文件（{size}），但仍有 {failed} 个"
            "正在使用或无法删除的文件或文件夹。"
        ),
        "display_group": "屏幕与立绘",
        "display_help_title": "屏幕与立绘说明",
        "display_help_body": (
            "屏幕编号：当前屏幕列表中从 0 开始的序号。"
            "序号不可用时会回退到主屏幕。\n\n"
            "立绘高度比例：角色立绘相对于所选屏幕可用高度的目标比例。\n\n"
            "实时日志命令行：打开实时日志窗口，用于排查模型、TTS、录音及"
            "其他运行问题。"
        ),
        "screen_index": "屏幕编号",
        "portrait_ratio": "立绘高度比例",
        "show_log_console": "打开实时日志命令行",
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


logger = get_logger("settings")


class ModelListWorker(QThread):
    models_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        settings: AppSettings,
        *,
        vision: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.vision = vision

    def run(self) -> None:
        try:
            backend = (
                create_vision_backend(self.settings)
                if self.vision
                else create_backend(self.settings)
            )
            self.models_ready.emit(
                backend.list_models(vision=self.vision)
            )
        except Exception as exc:
            logger.exception(
                "%s模型列表加载失败",
                "视觉" if self.vision else "语言",
            )
            self.error.emit(str(exc))


class WhisperModelCheckWorker(QThread):
    checked = pyqtSignal(str, str, str)

    def __init__(
        self,
        model_name: str,
        model_directory: str,
        parent=None,
    ):
        super().__init__(parent)
        self.model_name = model_name
        self.model_directory = model_directory

    def run(self) -> None:
        path = find_local_model(
            self.model_name,
            self.model_directory,
        ) or ""
        self.checked.emit(self.model_name, self.model_directory, path)


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
        password: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings.model_copy(deep=True)
        self.action = action
        self.password = password

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
            if not self.settings.uses_autodl() and not state.model_ready:
                raise TTSServiceError(
                    "The Murasame voice weights are incomplete."
                )
            if (
                not self.settings.uses_autodl()
                and not state.reference_voices_ready
            ):
                raise TTSServiceError(
                    "The Murasame reference voices are incomplete."
                )
            manager.ensure_running(
                self.settings,
                state=state,
                progress=self.stage_changed.emit,
                password=self.password,
            )
            if not self.settings.uses_autodl():
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

    clear_history_requested = pyqtSignal()

    def __init__(
        self,
        settings: AppSettings,
        *,
        first_run: bool = False,
        download_manager: DownloadManager | None = None,
        parent=None,
        platform_runtime: PlatformRuntime | None = None,
    ):
        super().__init__(parent)
        self._platform_runtime = (
            platform_runtime or get_platform_runtime()
        )
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._original = settings.model_copy(deep=True)
        self._first_run = first_run
        self._model_worker: ModelListWorker | None = None
        self._model_target: tuple[str, str, str] | None = None
        self._model_fetch_queue: list[bool] = []
        self._auto_models_requested = False
        self._whisper_check_worker: WhisperModelCheckWorker | None = None
        self._pending_whisper_model: tuple[str, str] | None = None
        self._tts_check_worker: TTSCheckWorker | None = None
        self._tts_service_worker: TTSServiceWorker | None = None
        self._tts_service_error: str | None = None
        self._tts_service_button_mode = "start"
        self._pending_tts_check = False
        self._tts_download_prompted = False
        self._tts_engine_download_needed = False
        self._closing = False
        self._result: AppSettings | None = None
        self.download_manager = download_manager or DownloadManager(
            QApplication.instance(),
            platform_runtime=self._platform_runtime,
        )
        self._form_labels: dict[str, list[QLabel]] = {}
        self._form_fields: dict[str, list[QWidget]] = {}
        self._audio_device_signature: tuple[object, ...] | None = None
        self._status_key: str | None = None
        self._status_values: dict[str, object] = {}
        self._whisper_status_key = "whisper_disabled"
        self._whisper_status_values: dict[str, object] = {}
        self._tts_status_key = "tts_disabled"
        self._tts_status_values: dict[str, object] = {}

        self.setMinimumSize(700, 650)
        self.resize(760, 720)
        root = QVBoxLayout(self)

        language_form = QFormLayout()
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh-CN")
        language_form.addRow(self.language_label, self.language_combo)
        root.addLayout(language_form)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_models_tab(), "")
        self.tabs.addTab(self._build_extensions_tab(), "")
        self.tabs.addTab(self._build_character_tab(), "")
        self.tabs.addTab(self._build_automation_tab(), "")
        self.tabs.addTab(self._build_display_tab(), "")
        self.tabs.addTab(self._build_other_tab(), "")
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

        self._audio_device_refresh_timer = QTimer(self)
        self._audio_device_refresh_timer.setInterval(2_000)
        self._audio_device_refresh_timer.timeout.connect(
            self._refresh_audio_input_devices
        )
        self._load_values(settings)
        self.language_combo.currentIndexChanged.connect(
            self._on_language_changed
        )
        self.stt_enabled.toggled.connect(self._update_whisper_state)
        self.stt_model.currentTextChanged.connect(self._update_whisper_state)
        self.whisper_model_dir.editingFinished.connect(
            self._update_whisper_state
        )
        self.vision_enabled.toggled.connect(self._update_vision_state)
        self.tts_enabled.toggled.connect(self._update_tts_state)
        self.tts_backend.currentIndexChanged.connect(
            self._on_tts_backend_changed
        )
        self.tts_url.editingFinished.connect(self._update_tts_state)
        self.tts_engine_root.editingFinished.connect(self._update_tts_state)
        self.tts_model_dir.editingFinished.connect(self._update_tts_state)
        self.tts_autodl_ssh_command.editingFinished.connect(
            self._update_tts_state
        )
        self.tts_autodl_password.editingFinished.connect(
            self._update_tts_state
        )
        self.tts_autodl_remote_command.editingFinished.connect(
            self._update_tts_state
        )
        self.tts_autodl_reference_root.editingFinished.connect(
            self._update_tts_state
        )
        self.download_manager.changed.connect(self._on_download_changed)
        self._update_backend_visibility()
        self._retranslate_ui()
        self._update_vision_state(self.vision_enabled.isChecked())
        self._update_whisper_state()
        self._update_tts_state()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_audio_input_devices()
        self._audio_device_refresh_timer.start()
        if self._auto_models_requested:
            return
        self._auto_models_requested = True
        QTimer.singleShot(0, self._auto_fetch_models)

    def hideEvent(self, event) -> None:
        self._audio_device_refresh_timer.stop()
        super().hideEvent(event)

    def _add_row(
        self,
        form: QFormLayout,
        key: str,
        field: QWidget,
    ) -> None:
        label = QLabel()
        label.setWordWrap(True)
        form.addRow(label, field)
        self._form_labels.setdefault(key, []).append(label)
        self._form_fields.setdefault(key, []).append(field)

    def _set_form_labels_enabled(
        self,
        keys: tuple[str, ...],
        enabled: bool,
    ) -> None:
        for key in keys:
            for label in self._form_labels.get(key, ()):
                label.setEnabled(enabled)

    def _set_form_rows_visible(
        self,
        keys: tuple[str, ...],
        visible: bool,
    ) -> None:
        for key in keys:
            for label in self._form_labels.get(key, ()):
                label.setVisible(visible)
            for field in self._form_fields.get(key, ()):
                field.setVisible(visible)

    def _help_button(self, title_key: str, body_key: str) -> QToolButton:
        button = QToolButton()
        button.setText("?")
        button.setFixedSize(24, 24)
        button.clicked.connect(
            lambda: QMessageBox.information(
                self,
                self._text(title_key),
                self._text(body_key),
            )
        )
        return button

    @staticmethod
    def _right_aligned_widget(widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(widget)
        return container

    def _build_models_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSizeConstraint(QLayout.SetMinimumSize)

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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _build_ollama_panel(self) -> QWidget:
        self.ollama_group = QGroupBox()
        form = QFormLayout(self.ollama_group)
        self.ollama_url = QLineEdit()
        self.ollama_chat_model = self._editable_combo()
        self.ollama_context_window = self._spinbox(2_048, 131_072)
        self.ollama_context_window.setSingleStep(1_024)
        self.ollama_timeout = self._spinbox(10, 600)
        self.ollama_keep_alive = QLineEdit()
        self._add_row(form, "server_url", self.ollama_url)
        self._add_row(form, "chat_model", self.ollama_chat_model)
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
        self.api_provider.addItem("OpenAI", "openai")
        self.api_provider.currentIndexChanged.connect(
            self._update_api_provider
        )
        self._add_row(provider_form, "provider", self.api_provider)
        layout.addLayout(provider_form)

        self.api_provider_stack = QStackedWidget()
        self.api_provider_stack.addWidget(self._build_deepseek_panel())
        self.api_provider_stack.addWidget(self._build_aliyun_panel())
        self.api_provider_stack.addWidget(self._build_openai_panel())
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
        self._add_row(form, "aliyun_api_key", self.aliyun_key)
        self._add_row(form, "base_url", self.aliyun_url)
        self._add_row(form, "chat_model", self.aliyun_chat_model)
        return panel

    def _build_openai_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.openai_key = self._password_field()
        self.openai_url = QLineEdit()
        self.openai_chat_model = self._editable_combo()
        self.openai_chat_model.addItems(
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"]
        )
        self._add_row(form, "openai_api_key", self.openai_key)
        self._add_row(form, "base_url", self.openai_url)
        self._add_row(form, "chat_model", self.openai_chat_model)
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
        self.outfit = QComboBox()
        self.outfit.addItem("", "sleepwear")
        self.outfit.addItem("", "casual")
        self.outfit.addItem("", "uniform")
        self.outfit.addItem("", "kimono")
        self._add_row(identity_form, "user_name", self.user_name)
        self._add_row(identity_form, "portrait_set", self.portrait)
        self._add_row(identity_form, "outfit", self.outfit)
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

    def _build_extensions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.vision_group = QGroupBox()
        vision_layout = QVBoxLayout(self.vision_group)
        self.vision_enabled = QCheckBox()
        vision_layout.addWidget(self.vision_enabled)

        self.vision_options = QWidget()
        vision_options_layout = QVBoxLayout(self.vision_options)
        vision_options_layout.setContentsMargins(0, 0, 0, 0)
        vision_provider_form = QFormLayout()
        self.vision_provider = QComboBox()
        self.vision_provider.addItem("", "ollama")
        self.vision_provider.addItem("", "aliyun")
        self.vision_provider.addItem("", "openai")
        self.vision_provider.currentIndexChanged.connect(
            self._update_vision_compatibility
        )
        self._add_row(
            vision_provider_form,
            "vision_provider",
            self.vision_provider,
        )
        vision_options_layout.addLayout(vision_provider_form)

        self.vision_provider_stack = QStackedWidget()
        self.vision_provider_stack.addWidget(
            self._build_vision_ollama_panel()
        )
        self.vision_provider_stack.addWidget(
            self._build_vision_aliyun_panel()
        )
        self.vision_provider_stack.addWidget(
            self._build_vision_openai_panel()
        )
        vision_options_layout.addWidget(self.vision_provider_stack)

        vision_model_row = QHBoxLayout()
        self.fetch_vision_models_button = QPushButton()
        self.fetch_vision_models_button.clicked.connect(
            self._fetch_vision_models
        )
        vision_model_row.addWidget(self.fetch_vision_models_button)
        vision_model_row.addStretch(1)
        vision_options_layout.addLayout(vision_model_row)
        self.vision_model_list_help = QLabel()
        self.vision_model_list_help.setWordWrap(True)
        vision_options_layout.addWidget(self.vision_model_list_help)

        vision_form = QFormLayout()
        self.vision_interval = self._spinbox(10, 86_400)
        self.vision_timeout = self._spinbox(10, 600)
        self.vision_compatibility = QLabel()
        self.vision_compatibility.setWordWrap(True)
        self._add_row(vision_form, "interval", self.vision_interval)
        self._add_row(
            vision_form,
            "request_timeout",
            self.vision_timeout,
        )
        vision_form.addRow(self.vision_compatibility)
        vision_options_layout.addLayout(vision_form)
        vision_layout.addWidget(self.vision_options)

        self.tts_group = QGroupBox()
        tts_form = QFormLayout(self.tts_group)
        self.tts_enabled = QCheckBox()
        self.tts_backend = QComboBox()
        self.tts_backend.addItem("", "local")
        self.tts_backend.addItem("", "autodl")
        self.tts_url = QLineEdit()
        self.tts_timeout = self._spinbox(10, 900)
        self.tts_engine_root = QLineEdit()
        self.tts_engine_browse = QPushButton()
        self.tts_engine_browse.clicked.connect(self._browse_tts_engine)
        self.tts_model_dir = QLineEdit()
        self.tts_model_browse = QPushButton()
        self.tts_model_browse.clicked.connect(self._browse_tts_model)
        self.tts_autodl_ssh_command = QLineEdit()
        self.tts_autodl_password = self._password_field()
        self.tts_autodl_remote_command = QLineEdit()
        self.tts_autodl_reference_root = QLineEdit()
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
        self.whisper_model_dir = QLineEdit()
        self.whisper_model_browse = QPushButton()
        self.whisper_model_browse.clicked.connect(
            self._browse_whisper_model
        )
        self.stt_device = QComboBox()
        self.stt_device.addItem("", "auto")
        self.stt_device.addItem("", "cuda")
        self.stt_device.addItem("", "cpu")
        self.stt_input_device = QComboBox()
        self._default_audio_input = None
        self._missing_audio_input_identifier = ""
        self.stt_input_device.addItem("", "")
        self._refresh_audio_input_devices(force=True)
        self.whisper_status = QLabel()
        self.whisper_status.setWordWrap(True)
        self.whisper_progress = QProgressBar()
        self.whisper_progress.setTextVisible(True)
        self.whisper_progress.hide()
        self.whisper_download_button = QPushButton()
        self.whisper_download_button.clicked.connect(
            self._download_whisper_model
        )
        tts_form.addRow(self.tts_enabled)
        self._add_row(tts_form, "tts_backend", self.tts_backend)
        self._add_row(tts_form, "tts_endpoint", self.tts_url)
        self._add_row(tts_form, "tts_timeout", self.tts_timeout)
        self._add_row(
            tts_form,
            "tts_engine_root",
            self._path_picker(
                self.tts_engine_root,
                self.tts_engine_browse,
            ),
        )
        self._add_row(
            tts_form,
            "tts_model_dir",
            self._path_picker(
                self.tts_model_dir,
                self.tts_model_browse,
            ),
        )
        self._add_row(
            tts_form,
            "tts_autodl_ssh_command",
            self.tts_autodl_ssh_command,
        )
        self._add_row(
            tts_form,
            "tts_autodl_password",
            self.tts_autodl_password,
        )
        self._add_row(
            tts_form,
            "tts_autodl_remote_command",
            self.tts_autodl_remote_command,
        )
        self._add_row(
            tts_form,
            "tts_autodl_reference_root",
            self.tts_autodl_reference_root,
        )
        tts_form.addRow(self.tts_status)
        tts_form.addRow(self.tts_service_button)
        tts_form.addRow(self.tts_progress)
        tts_form.addRow(self.tts_extract_progress)
        tts_form.addRow(self.tts_download_button)
        layout.addWidget(self.tts_group)

        self.whisper_group = QGroupBox()
        whisper_form = QFormLayout(self.whisper_group)
        whisper_form.addRow(self.stt_enabled)
        self._add_row(whisper_form, "whisper_model", self.stt_model)
        self._add_row(
            whisper_form,
            "whisper_model_dir",
            self._path_picker(
                self.whisper_model_dir,
                self.whisper_model_browse,
            ),
        )
        whisper_form.addRow(self.whisper_status)
        whisper_form.addRow(self.whisper_progress)
        whisper_form.addRow(self.whisper_download_button)
        self._add_row(
            whisper_form,
            "stt_input_device",
            self.stt_input_device,
        )
        self._add_row(whisper_form, "stt_device", self.stt_device)
        layout.addWidget(self.whisper_group)
        layout.addWidget(self.vision_group)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _build_vision_ollama_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.vision_ollama_url = QLineEdit()
        self.vision_ollama_model = self._editable_combo()
        self.vision_ollama_context_window = self._spinbox(
            2_048,
            131_072,
        )
        self.vision_ollama_context_window.setSingleStep(1_024)
        self.vision_ollama_keep_alive = QLineEdit()
        self._add_row(form, "server_url", self.vision_ollama_url)
        self._add_row(form, "vision_model", self.vision_ollama_model)
        self._add_row(
            form,
            "context_window",
            self.vision_ollama_context_window,
        )
        self._add_row(
            form,
            "keep_alive",
            self.vision_ollama_keep_alive,
        )
        return panel

    def _build_vision_aliyun_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.vision_aliyun_key = self._password_field()
        self.vision_aliyun_url = QLineEdit()
        self.vision_aliyun_model = self._editable_combo()
        self._add_row(
            form,
            "aliyun_api_key",
            self.vision_aliyun_key,
        )
        self._add_row(form, "base_url", self.vision_aliyun_url)
        self._add_row(form, "vision_model", self.vision_aliyun_model)
        return panel

    def _build_vision_openai_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.vision_openai_key = self._password_field()
        self.vision_openai_url = QLineEdit()
        self.vision_openai_model = self._editable_combo()
        self.vision_openai_model.addItems(
            ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"]
        )
        self._add_row(
            form,
            "openai_api_key",
            self.vision_openai_key,
        )
        self._add_row(form, "base_url", self.vision_openai_url)
        self._add_row(form, "vision_model", self.vision_openai_model)
        return panel

    def _build_automation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.automation_group = QGroupBox()
        behavior_form = QFormLayout(self.automation_group)
        self.automation_help_button = self._help_button(
            "automation_help_title",
            "automation_help_body",
        )
        behavior_form.addRow(
            self._right_aligned_widget(self.automation_help_button)
        )
        self.thinking_minutes = self._spinbox(1, 1_440)
        self.away_minutes = self._spinbox(2, 1_440)
        self.history_limit = self._spinbox(4, 200)
        self.do_not_disturb = QCheckBox()
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
        behavior_form.addRow(self.do_not_disturb)
        layout.addWidget(self.automation_group)
        layout.addStretch(1)
        return page

    def _build_display_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.display_group = QGroupBox()
        display_form = QFormLayout(self.display_group)
        self.display_help_button = self._help_button(
            "display_help_title",
            "display_help_body",
        )
        display_form.addRow(
            self._right_aligned_widget(self.display_help_button)
        )
        self.screen_index = self._spinbox(0, 32)
        self.portrait_ratio = QDoubleSpinBox()
        self.portrait_ratio.setRange(0.2, 1.0)
        self.portrait_ratio.setSingleStep(0.05)
        self.portrait_ratio.setDecimals(2)
        self.show_log_console = QCheckBox()
        self._add_row(display_form, "screen_index", self.screen_index)
        self._add_row(
            display_form,
            "portrait_ratio",
            self.portrait_ratio,
        )
        display_form.addRow(self.show_log_console)
        layout.addWidget(self.display_group)
        layout.addStretch(1)
        return page

    def _build_other_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.data_group = QGroupBox()
        data_form = QFormLayout(self.data_group)
        self.clear_history_button = QPushButton()
        self.clear_history_button.setEnabled(not self._first_run)
        self.clear_history_button.clicked.connect(
            self._confirm_clear_history
        )
        self.clear_cache_button = QPushButton()
        self.clear_cache_button.clicked.connect(self._confirm_clear_cache)
        self._add_row(
            data_form,
            "conversation_history_data",
            self.clear_history_button,
        )
        self._add_row(
            data_form,
            "runtime_cache_data",
            self.clear_cache_button,
        )
        layout.addWidget(self.data_group)
        layout.addStretch(1)
        return page

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
        self.openai_key.setText(settings.api.openai_api_key)
        self.openai_url.setText(settings.api.openai_base_url)
        self._set_editable_combo(
            self.openai_chat_model,
            settings.api.openai_chat_model,
        )
        self.api_timeout.setValue(settings.api.timeout_seconds)

        self.user_name.setText(settings.character.user_name)
        self._set_combo_data(self.portrait, settings.character.portrait)
        self._set_combo_data(self.outfit, settings.character.outfit)
        try:
            self.personality_prompt.setPlainText(load_personality(settings))
        except OSError:
            self.personality_prompt.clear()

        self.vision_enabled.setChecked(settings.vision.enabled)
        self.vision_interval.setValue(settings.vision.interval_seconds)
        self.vision_timeout.setValue(settings.vision.timeout_seconds)
        self._set_combo_data(
            self.vision_provider,
            settings.vision.provider,
        )
        self.vision_ollama_url.setText(
            settings.vision.ollama_base_url
        )
        self._set_editable_combo(
            self.vision_ollama_model,
            settings.vision.ollama_model,
        )
        self.vision_ollama_context_window.setValue(
            settings.vision.ollama_context_window
        )
        self.vision_ollama_keep_alive.setText(
            settings.vision.ollama_keep_alive
        )
        self.vision_aliyun_key.setText(settings.vision.aliyun_api_key)
        self.vision_aliyun_url.setText(settings.vision.aliyun_base_url)
        self._set_editable_combo(
            self.vision_aliyun_model,
            settings.vision.aliyun_model,
        )
        self.vision_openai_key.setText(settings.vision.openai_api_key)
        self.vision_openai_url.setText(settings.vision.openai_base_url)
        self._set_editable_combo(
            self.vision_openai_model,
            settings.vision.openai_model,
        )
        self.tts_enabled.setChecked(settings.tts.enabled)
        self._set_combo_data(self.tts_backend, settings.tts.backend)
        self.tts_url.setText(settings.tts.base_url)
        self.tts_timeout.setValue(settings.tts.timeout_seconds)
        self.tts_engine_root.setText(settings.tts.engine_root)
        self.tts_model_dir.setText(settings.tts.model_dir)
        self.tts_autodl_ssh_command.setText(
            settings.tts.autodl_ssh_command
        )
        self.tts_autodl_remote_command.setText(
            settings.tts.autodl_remote_command
        )
        self.tts_autodl_reference_root.setText(
            settings.tts.autodl_remote_reference_root
        )
        self.stt_enabled.setChecked(settings.stt.enabled)
        self._set_editable_combo(self.stt_model, settings.stt.model)
        self.whisper_model_dir.setText(settings.stt.model_dir)
        self._set_audio_input_device(settings.stt.input_device)
        self._set_combo_data(self.stt_device, settings.stt.device)
        self.screen_index.setValue(settings.display.screen_index)
        self.portrait_ratio.setValue(
            settings.display.portrait_screen_ratio
        )
        self.show_log_console.setChecked(
            settings.display.show_log_console
        )
        self.thinking_minutes.setValue(settings.idle.thinking_minutes)
        self.away_minutes.setValue(settings.idle.away_minutes)
        self.do_not_disturb.setChecked(settings.idle.do_not_disturb)
        self.history_limit.setValue(settings.history_limit)

    def _language(self) -> str:
        language = self.language_combo.currentData()
        return language if language in TRANSLATIONS else "en"

    def _text(self, key: str, **values: object) -> str:
        text = TRANSLATIONS[self._language()][key]
        return text.format(**values) if values else text

    def _set_audio_input_device(self, identifier: str) -> None:
        index = self.stt_input_device.findData(identifier)
        if index < 0 and identifier:
            name, hostapi = decode_audio_input_device(identifier)
            description = f"{name} — {hostapi}" if hostapi else name
            self.stt_input_device.addItem(description, identifier)
            self._missing_audio_input_identifier = identifier
            index = self.stt_input_device.count() - 1
        self.stt_input_device.setCurrentIndex(max(index, 0))

    def _refresh_audio_input_devices(self, force: bool = False) -> None:
        if not hasattr(self, "stt_input_device"):
            return
        default_device, input_devices = refresh_audio_input_devices()
        signature: tuple[object, ...] = (
            (
                default_device.identifier,
                default_device.display_name,
            )
            if default_device is not None
            else None,
            tuple(
                (device.identifier, device.display_name)
                for device in input_devices
            ),
        )
        if not force and signature == self._audio_device_signature:
            return

        selected = self.stt_input_device.currentData() or ""
        self._audio_device_signature = signature
        self._default_audio_input = default_device
        self._missing_audio_input_identifier = ""
        self.stt_input_device.blockSignals(True)
        try:
            self.stt_input_device.clear()
            self.stt_input_device.addItem("", "")
            for input_device in input_devices:
                self.stt_input_device.addItem(
                    input_device.display_name,
                    input_device.identifier,
                )
            self._set_audio_input_device(selected)
            self._retranslate_audio_input_devices()
        finally:
            self.stt_input_device.blockSignals(False)

    def _retranslate_audio_input_devices(self) -> None:
        default_name = (
            self._default_audio_input.name
            if self._default_audio_input is not None
            else ""
        )
        default_text = (
            self._text("stt_input_default", device=default_name)
            if default_name
            else self._text("stt_input_default_unknown")
        )
        self._set_combo_item_text(
            self.stt_input_device,
            "",
            default_text,
        )
        if self._missing_audio_input_identifier:
            name, hostapi = decode_audio_input_device(
                self._missing_audio_input_identifier
            )
            description = f"{name} — {hostapi}" if hostapi else name
            self._set_combo_item_text(
                self.stt_input_device,
                self._missing_audio_input_identifier,
                self._text(
                    "stt_input_unavailable",
                    device=description,
                ),
            )

    def _on_language_changed(self) -> None:
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        title_key = "title_setup" if self._first_run else "title_settings"
        self.setWindowTitle(self._text(title_key))
        self.language_label.setText(self._text("language"))
        self.tabs.setTabText(0, self._text("tab_models"))
        self.tabs.setTabText(1, self._text("tab_extensions"))
        self.tabs.setTabText(2, self._text("tab_character"))
        self.tabs.setTabText(3, self._text("tab_automation"))
        self.tabs.setTabText(4, self._text("tab_display"))
        self.tabs.setTabText(5, self._text("tab_other"))

        self.backend_group.setTitle(self._text("backend_group"))
        self.ollama_group.setTitle(self._text("ollama_group"))
        self.api_group.setTitle(self._text("api_group"))
        self.identity_group.setTitle(self._text("identity_group"))
        self.prompt_group.setTitle(self._text("prompt_group"))
        self.vision_group.setTitle(self._text("vision_group"))
        self.tts_group.setTitle(self._text("tts_group"))
        self.whisper_group.setTitle(self._text("whisper_group"))
        self.automation_group.setTitle(self._text("automation_group"))
        self.display_group.setTitle(self._text("display_group"))
        self.data_group.setTitle(self._text("data_group"))

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
            self.api_provider,
            "openai",
            self._text("provider_openai"),
        )
        self._set_combo_item_text(
            self.vision_provider,
            "ollama",
            self._text("vision_provider_ollama"),
        )
        self._set_combo_item_text(
            self.vision_provider,
            "aliyun",
            self._text("vision_provider_aliyun"),
        )
        self._set_combo_item_text(
            self.vision_provider,
            "openai",
            self._text("vision_provider_openai"),
        )
        self._set_combo_item_text(
            self.tts_backend,
            "local",
            self._text("tts_backend_local"),
        )
        self._set_combo_item_text(
            self.tts_backend,
            "autodl",
            self._text("tts_backend_autodl"),
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
        for outfit in ("sleepwear", "casual", "uniform", "kimono"):
            self._set_combo_item_text(
                self.outfit,
                outfit,
                self._text(f"outfit_{outfit}"),
            )

        self.deepseek_thinking.setText(self._text("deepseek_thinking"))
        self.do_not_disturb.setText(self._text("do_not_disturb"))
        self.automation_help_button.setToolTip(self._text("settings_help"))
        self.automation_help_button.setAccessibleName(
            self._text("settings_help")
        )
        self.display_help_button.setToolTip(self._text("settings_help"))
        self.display_help_button.setAccessibleName(
            self._text("settings_help")
        )
        self.clear_history_button.setText(self._text("clear_history"))
        self.clear_history_button.setToolTip(
            (
                ""
                if not self._first_run
                else self._text("history_unavailable_first_run")
            )
        )
        self.clear_cache_button.setText(self._text("clear_cache"))
        self.deepseek_note.setText(self._text("deepseek_note"))
        self.fetch_models_button.setText(self._text("load_models"))
        self.model_list_help.setText(self._text("model_list_help"))
        self.fetch_vision_models_button.setText(
            self._text("load_vision_models")
        )
        self.vision_model_list_help.setText(
            self._text("vision_model_list_help")
        )
        self.prompt_help.setText(self._text("prompt_help"))
        self.personality_prompt.setPlaceholderText(
            self._text("prompt_placeholder")
        )
        self.import_button.setText(self._text("import_prompt"))
        self.vision_enabled.setText(self._text("vision_enabled"))
        self.show_log_console.setText(
            self._text("show_log_console")
        )
        self.tts_enabled.setText(self._text("tts_enabled"))
        self.tts_autodl_password.setPlaceholderText(
            self._text("tts_autodl_password_placeholder")
        )
        self.tts_engine_browse.setText(self._text("browse"))
        self.tts_model_browse.setText(self._text("browse"))
        self.tts_download_button.setText(self._text("tts_download"))
        self._render_tts_service_button()
        self.stt_enabled.setText(self._text("stt_enabled"))
        self._retranslate_audio_input_devices()
        self._set_combo_item_text(
            self.stt_device,
            "auto",
            self._text("stt_device_auto"),
        )
        self._set_combo_item_text(
            self.stt_device,
            "cuda",
            self._text("stt_device_cuda"),
        )
        self._set_combo_item_text(
            self.stt_device,
            "cpu",
            self._text("stt_device_cpu"),
        )
        self.whisper_download_button.setText(
            self._text("whisper_download")
        )
        self.whisper_model_browse.setText(self._text("browse"))
        self.deepseek_key.setPlaceholderText(
            self._text("password_placeholder")
        )
        self.aliyun_key.setPlaceholderText(
            self._text("password_placeholder")
        )
        self.openai_key.setPlaceholderText(
            self._text("password_placeholder")
        )
        self.vision_aliyun_key.setPlaceholderText(
            self._text("password_placeholder")
        )
        self.vision_openai_key.setPlaceholderText(
            self._text("password_placeholder")
        )

        seconds = self._text("seconds")
        for spinbox in (
            self.ollama_timeout,
            self.api_timeout,
            self.vision_interval,
            self.vision_timeout,
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
        model_directory = self.whisper_model_dir.text().strip()
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
        self.whisper_model_dir.setEnabled(enabled and not downloading)
        self.whisper_model_browse.setEnabled(enabled and not downloading)
        self.stt_device.setEnabled(enabled)
        self.stt_input_device.setEnabled(enabled)
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
            self._pending_whisper_model = (
                model_name,
                model_directory,
            )
            self._set_whisper_status("whisper_checking")
            return
        self._start_whisper_check(model_name, model_directory)

    def _start_whisper_check(
        self,
        model_name: str,
        model_directory: str,
    ) -> None:
        self._set_whisper_status("whisper_checking")
        worker = WhisperModelCheckWorker(
            model_name,
            model_directory,
            self,
        )
        self._whisper_check_worker = worker
        worker.checked.connect(self._on_whisper_checked)
        worker.finished.connect(
            lambda: self._finish_whisper_check(worker)
        )
        worker.start()

    def _on_whisper_checked(
        self,
        model_name: str,
        model_directory: str,
        path: str,
    ) -> None:
        if (
            not self.stt_enabled.isChecked()
            or model_name != self.stt_model.currentText().strip()
            or model_directory != self.whisper_model_dir.text().strip()
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
                is_path = looks_like_local_model_path(model_name)
                self.whisper_download_button.setEnabled(not is_path)
                self._set_whisper_status(
                    "whisper_path_missing" if is_path else "whisper_missing"
                )

    def _finish_whisper_check(
        self,
        worker: WhisperModelCheckWorker,
    ) -> None:
        if self._whisper_check_worker is worker:
            self._whisper_check_worker = None
        worker.deleteLater()
        if self._closing:
            self._pending_whisper_model = None
            return
        pending = self._pending_whisper_model
        self._pending_whisper_model = None
        current = (
            self.stt_model.currentText().strip(),
            self.whisper_model_dir.text().strip(),
        )
        if (
            self.stt_enabled.isChecked()
            and pending
            and pending == current
        ):
            self._start_whisper_check(*pending)

    def _download_whisper_model(self) -> None:
        model_name = self.stt_model.currentText().strip()
        if (
            not self.stt_enabled.isChecked()
            or not model_name
            or looks_like_local_model_path(model_name)
        ):
            return

        destination = self._require_download_directory(
            self.whisper_model_dir,
            "whisper_path_required",
        )
        if destination is None:
            return
        job_id = self.download_manager.start_whisper(
            model_name,
            destination,
        )
        snapshot = self.download_manager.snapshot(job_id)
        self.whisper_download_button.setEnabled(False)
        self.stt_model.setEnabled(False)
        self.whisper_model_dir.setEnabled(False)
        self.whisper_model_browse.setEnabled(False)
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

    def _on_tts_backend_changed(self) -> None:
        manager = get_tts_service_manager()
        if manager.owns_running_process():
            manager.stop()
        if self.tts_backend.currentData() == "autodl":
            self.tts_url.setText("http://127.0.0.1:9880/tts")
        self._update_tts_state()

    def _current_tts_settings(
        self,
        *,
        enabled: bool | None = None,
    ) -> TTSSettings:
        return TTSSettings(
            enabled=(
                self.tts_enabled.isChecked()
                if enabled is None
                else enabled
            ),
            backend=self.tts_backend.currentData() or "local",
            base_url=self.tts_url.text().strip(),
            engine_root=self.tts_engine_root.text().strip(),
            model_dir=self.tts_model_dir.text().strip(),
            autodl_ssh_command=(
                self.tts_autodl_ssh_command.text().strip()
            ),
            autodl_remote_command=(
                self.tts_autodl_remote_command.text().strip()
            ),
            autodl_remote_reference_root=(
                self.tts_autodl_reference_root.text().strip()
            ),
            autodl_password_encrypted=(
                self._original.tts.autodl_password_encrypted
            ),
            timeout_seconds=self.tts_timeout.value(),
        )

    def _set_tts_path_controls(self, *, downloading: bool) -> None:
        enabled = self.tts_enabled.isChecked()
        autodl = self.tts_backend.currentData() == "autodl"
        controls_enabled = enabled and not downloading
        local_enabled = controls_enabled and not autodl
        autodl_enabled = controls_enabled and autodl
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

        self.tts_backend.setEnabled(controls_enabled)
        self.tts_timeout.setEnabled(controls_enabled)
        self.tts_url.setEnabled(local_enabled)
        self.tts_engine_root.setEnabled(local_enabled)
        self.tts_engine_browse.setEnabled(local_enabled)
        self.tts_model_dir.setEnabled(local_enabled)
        self.tts_model_browse.setEnabled(local_enabled)
        for field in (
            self.tts_autodl_ssh_command,
            self.tts_autodl_password,
            self.tts_autodl_remote_command,
            self.tts_autodl_reference_root,
        ):
            field.setEnabled(autodl_enabled)

        self._set_form_rows_visible(local_keys, not autodl)
        self._set_form_rows_visible(autodl_keys, autodl)
        self.tts_download_button.setVisible(not autodl)
        if autodl:
            self.tts_progress.hide()
            self.tts_extract_progress.hide()

        self._set_form_labels_enabled(
            ("tts_backend", "tts_timeout"),
            controls_enabled,
        )
        self._set_form_labels_enabled(
            local_keys,
            local_enabled,
        )
        self._set_form_labels_enabled(
            autodl_keys,
            autodl_enabled,
        )

    def _update_tts_state(self) -> None:
        if not hasattr(self, "tts_status"):
            return
        enabled = self.tts_enabled.isChecked()
        autodl = self.tts_backend.currentData() == "autodl"
        snapshot = self.download_manager.snapshot(TTS_JOB_ID)
        downloading = snapshot.status in {
            "preparing",
            "checking",
            "downloading",
            "extracting",
            "installing",
            "cleaning",
        }
        self._set_tts_path_controls(downloading=downloading)
        self.tts_download_button.setEnabled(False)
        self.tts_service_button.setVisible(True)
        self._set_tts_service_button("start", False)
        if (
            self._tts_service_worker is not None
            and self._tts_service_worker.isRunning()
        ):
            return
        if downloading:
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
            settings = self._current_tts_settings(enabled=True)
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
        if self._closing or not self.tts_enabled.isChecked():
            return
        autodl = self.tts_backend.currentData() == "autodl"
        if autodl:
            self._tts_engine_download_needed = False
            if reachable:
                if get_tts_service_manager().owns_running_process():
                    self._set_tts_service_button("stop", True)
                else:
                    self._set_tts_service_button("online", False)
                self._set_tts_status("tts_external_online")
            else:
                has_password = bool(
                    self.tts_autodl_password.text()
                    or self._original.tts.autodl_password_encrypted
                )
                can_start = bool(
                    self.tts_autodl_ssh_command.text().strip()
                    and self.tts_autodl_remote_command.text().strip()
                    and has_password
                )
                self._set_tts_service_button("start", can_start)
                self._set_tts_status("tts_external_offline")
            return

        configured_engine = self.tts_engine_root.text().strip()
        if state.engine_root is not None and not configured_engine:
            self.tts_engine_root.setText(str(state.engine_root))
        if (
            state.model_directory is not None
            and not self.tts_model_dir.text().strip()
        ):
            self.tts_model_dir.setText(str(state.model_directory))

        self._tts_engine_download_needed = (
            self._platform_runtime.capabilities.managed_archives
            and not reachable
            and not state.engine_ready
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
                self.tts_download_button.setEnabled(
                    self._platform_runtime.capabilities.managed_archives
                )
                self._set_tts_status("tts_engine_missing")
            elif not state.engine_ready:
                self.tts_download_button.setEnabled(
                    self._platform_runtime.capabilities.managed_archives
                )
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
            settings = self._current_tts_settings(enabled=True)
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
            else (
                "tts_service_connecting_ssh"
                if settings.uses_autodl()
                else "tts_service_locating"
            )
        )
        worker = TTSServiceWorker(
            settings,
            action,
            self.tts_autodl_password.text(),
            self,
        )
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
            "connecting_ssh": "tts_service_connecting_ssh",
            "starting_remote": "tts_service_starting_remote",
            "starting_tunnel": "tts_service_starting_tunnel",
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
        if self._closing:
            return
        if self._tts_service_error is None:
            self._update_tts_state()
        else:
            self.tts_service_button.setEnabled(True)

    def _request_tts_download(self) -> None:
        if not self.tts_enabled.isChecked():
            return
        if self.tts_backend.currentData() == "autodl":
            return
        model_destination = self._require_download_directory(
            self.tts_model_dir,
            "tts_model_path_required",
        )
        if model_destination is None:
            return
        engine_destination = None
        if self._tts_engine_download_needed:
            engine_destination = self._require_download_directory(
                self.tts_engine_root,
                "tts_engine_path_required",
            )
            if engine_destination is None:
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
        self.download_manager.start_tts(
            model_destination,
            include_engine=self._tts_engine_download_needed,
            engine_destination=engine_destination,
        )
        self._set_tts_path_controls(downloading=True)
        self.tts_download_button.setEnabled(False)
        self._render_tts_download(
            self.download_manager.snapshot(TTS_JOB_ID)
        )

    def _finish_tts_check(self, worker: TTSCheckWorker) -> None:
        if self._tts_check_worker is worker:
            self._tts_check_worker = None
        worker.deleteLater()
        if self._closing:
            self._pending_tts_check = False
            return
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
                self._set_tts_path_controls(downloading=True)
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
                self._set_tts_path_controls(downloading=False)
                self.tts_download_button.setEnabled(
                    self.tts_enabled.isChecked()
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
            self.whisper_model_dir.setEnabled(
                self.stt_enabled.isChecked()
            )
            self.whisper_model_browse.setEnabled(
                self.stt_enabled.isChecked()
            )
            self._render_progress(self.whisper_progress, snapshot)
            self._set_whisper_status(
                "whisper_downloaded",
                path=snapshot.destination,
            )
        elif snapshot.status == "failed":
            self.stt_model.setEnabled(self.stt_enabled.isChecked())
            self.whisper_model_dir.setEnabled(
                self.stt_enabled.isChecked()
            )
            self.whisper_model_browse.setEnabled(
                self.stt_enabled.isChecked()
            )
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

    def _browse_whisper_model(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._text("whisper_model_dir"),
            self.whisper_model_dir.text().strip() or str(Path.home()),
        )
        if selected:
            self.whisper_model_dir.setText(selected)
            self._update_whisper_state()

    def _require_download_directory(
        self,
        field: QLineEdit,
        missing_key: str,
    ) -> Path | None:
        value = field.text().strip()
        if not value:
            QMessageBox.warning(
                self,
                self._text("download_path_required_title"),
                self._text(missing_key),
            )
            return None
        directory = Path(value).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.is_dir():
                raise NotADirectoryError(str(directory))
            resolved = directory.resolve()
        except OSError as exc:
            QMessageBox.warning(
                self,
                self._text("download_path_required_title"),
                self._text("download_path_invalid", message=exc),
            )
            return None
        field.setText(str(resolved))
        return resolved

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
        provider_index = {
            "deepseek": 0,
            "aliyun": 1,
            "openai": 2,
        }
        self.api_provider_stack.setCurrentIndex(
            provider_index.get(provider, 0)
        )

    def _update_vision_compatibility(self) -> None:
        if not hasattr(self, "vision_provider_stack"):
            return
        provider_index = {
            "ollama": 0,
            "aliyun": 1,
            "openai": 2,
        }
        self.vision_provider_stack.setCurrentIndex(
            provider_index.get(self.vision_provider.currentData(), 0)
        )
        self.vision_compatibility.setText(
            self._text("vision_supported")
        )

    def _update_vision_state(self, enabled: bool) -> None:
        if not hasattr(self, "vision_options"):
            return
        self.vision_options.setEnabled(enabled)
        if not enabled:
            self._model_fetch_queue = [
                vision
                for vision in self._model_fetch_queue
                if not vision
            ]
        self._update_model_fetch_buttons()

    def _update_model_fetch_buttons(self) -> None:
        if not hasattr(self, "fetch_models_button"):
            return
        idle = self._model_worker is None
        self.fetch_models_button.setEnabled(idle)
        self.fetch_vision_models_button.setEnabled(
            idle and self.vision_enabled.isChecked()
        )

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

    def _confirm_clear_history(self) -> None:
        if self._first_run:
            return
        answer = QMessageBox.question(
            self,
            self._text("clear_history_confirm_title"),
            self._text("clear_history_confirm_body"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.clear_history_requested.emit()
        self._set_status("history_cleared")

    def _confirm_clear_cache(self) -> None:
        answer = QMessageBox.question(
            self,
            self._text("clear_cache_confirm_title"),
            self._text("clear_cache_confirm_body"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        result = clear_runtime_cache()
        values = {
            "files": result.removed_files,
            "size": self._format_byte_count(result.removed_bytes),
        }
        if result.failed_paths:
            self._set_status(
                "cache_clear_partial",
                failed=len(result.failed_paths),
                **values,
            )
        elif result.removed_files:
            self._set_status("cache_cleared", **values)
        else:
            self._set_status("cache_empty")

    @staticmethod
    def _format_byte_count(byte_count: int) -> str:
        size = float(max(0, byte_count))
        for unit in ("B", "KiB", "MiB", "GiB"):
            if size < 1024 or unit == "GiB":
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GiB"

    def _form_settings(self) -> AppSettings:
        personality_path = get_user_data_dir() / "personality.txt"
        screen_index = self.screen_index.value()
        original_display = self._original.display
        return AppSettings(
            ui_language=self._language(),
            mode=self.mode_combo.currentData(),
            ollama=OllamaSettings(
                base_url=self.ollama_url.text().strip(),
                chat_model=self.ollama_chat_model.currentText().strip(),
                context_window=self.ollama_context_window.value(),
                timeout_seconds=self.ollama_timeout.value(),
                keep_alive=self.ollama_keep_alive.text().strip(),
            ),
            api=APISettings(
                provider=self.api_provider.currentData(),
                deepseek_api_key=self.deepseek_key.text().strip(),
                aliyun_api_key=self.aliyun_key.text().strip(),
                openai_api_key=self.openai_key.text().strip(),
                deepseek_base_url=self.deepseek_url.text().strip(),
                aliyun_base_url=self.aliyun_url.text().strip(),
                openai_base_url=self.openai_url.text().strip(),
                deepseek_chat_model=(
                    self.deepseek_chat_model.currentText().strip()
                ),
                deepseek_thinking=self.deepseek_thinking.isChecked(),
                aliyun_chat_model=(
                    self.aliyun_chat_model.currentText().strip()
                ),
                openai_chat_model=(
                    self.openai_chat_model.currentText().strip()
                ),
                timeout_seconds=self.api_timeout.value(),
            ),
            vision=VisionSettings(
                enabled=self.vision_enabled.isChecked(),
                interval_seconds=self.vision_interval.value(),
                provider=self.vision_provider.currentData(),
                ollama_base_url=self.vision_ollama_url.text().strip(),
                ollama_model=(
                    self.vision_ollama_model.currentText().strip()
                ),
                ollama_context_window=(
                    self.vision_ollama_context_window.value()
                ),
                ollama_keep_alive=(
                    self.vision_ollama_keep_alive.text().strip()
                ),
                aliyun_api_key=self.vision_aliyun_key.text().strip(),
                aliyun_base_url=self.vision_aliyun_url.text().strip(),
                aliyun_model=(
                    self.vision_aliyun_model.currentText().strip()
                ),
                openai_api_key=self.vision_openai_key.text().strip(),
                openai_base_url=self.vision_openai_url.text().strip(),
                openai_model=(
                    self.vision_openai_model.currentText().strip()
                ),
                timeout_seconds=self.vision_timeout.value(),
            ),
            tts=self._current_tts_settings(),
            stt=STTSettings(
                enabled=self.stt_enabled.isChecked(),
                model=self.stt_model.currentText().strip(),
                model_dir=self.whisper_model_dir.text().strip(),
                device=self.stt_device.currentData(),
                input_device=self.stt_input_device.currentData() or "",
            ),
            character=CharacterSettings(
                user_name=self.user_name.text().strip(),
                portrait=self.portrait.currentData(),
                outfit=self.outfit.currentData(),
                personality_file=str(personality_path),
            ),
            display=DisplaySettings(
                screen_index=screen_index,
                screen_name=(
                    original_display.screen_name
                    if screen_index == original_display.screen_index
                    else ""
                ),
                window_x=original_display.window_x,
                window_y=original_display.window_y,
                portrait_screen_ratio=self.portrait_ratio.value(),
                show_log_console=self.show_log_console.isChecked(),
            ),
            idle=IdleSettings(
                do_not_disturb=self.do_not_disturb.isChecked(),
                thinking_minutes=self.thinking_minutes.value(),
                away_minutes=self.away_minutes.value(),
            ),
            history_limit=self.history_limit.value(),
        )

    def _fetch_models(self) -> None:
        self._start_model_fetch(vision=False)

    def _fetch_vision_models(self) -> None:
        if not self.vision_enabled.isChecked():
            return
        self._start_model_fetch(vision=True)

    def _auto_fetch_models(self) -> None:
        if self._closing:
            return
        try:
            settings = self._form_settings()
        except ValidationError:
            return

        scopes: list[bool] = []
        if (
            settings.mode == "ollama"
            or bool(settings.api.selected_api_key())
        ):
            scopes.append(False)
        if settings.vision.enabled and (
            settings.vision.provider == "ollama"
            or bool(settings.vision.selected_api_key())
        ):
            scopes.append(True)
        self._model_fetch_queue = scopes
        self._start_next_model_fetch()

    def _start_next_model_fetch(self) -> None:
        if (
            self._closing
            or self._model_worker is not None
            or not self._model_fetch_queue
        ):
            return
        self._start_model_fetch(
            vision=self._model_fetch_queue.pop(0),
            notify_if_busy=False,
        )

    def _start_model_fetch(
        self,
        *,
        vision: bool,
        notify_if_busy: bool = True,
    ) -> None:
        if vision and not self.vision_enabled.isChecked():
            return
        if self._model_worker is not None:
            if notify_if_busy:
                self._show_running_message()
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

        self.fetch_models_button.setEnabled(False)
        self.fetch_vision_models_button.setEnabled(False)
        self._set_status("connecting")
        self._model_target = (
            "vision" if vision else "chat",
            (
                settings.vision.provider
                if vision
                else settings.mode
            ),
            (
                settings.vision.provider
                if vision
                else settings.api.provider
            ),
        )
        worker = ModelListWorker(
            settings,
            vision=vision,
            parent=self,
        )
        self._model_worker = worker
        worker.models_ready.connect(self._on_models_ready)
        worker.error.connect(self._on_models_error)
        worker.finished.connect(lambda: self._finish_model_worker(worker))
        worker.start()

    def _finish_model_worker(self, worker: ModelListWorker) -> None:
        if self._model_worker is worker:
            self._model_worker = None
        worker.deleteLater()
        if self._model_fetch_queue and not self._closing:
            QTimer.singleShot(0, self._start_next_model_fetch)
            return
        self._update_model_fetch_buttons()

    def _on_models_ready(self, models: list[str]) -> None:
        if not models:
            self._set_status("models_empty")
            return

        scope, mode, provider = self._model_target or (
            "chat",
            self.mode_combo.currentData(),
            self.api_provider.currentData(),
        )
        targets: list[QComboBox]
        if scope == "vision":
            if provider == "ollama":
                targets = [self.vision_ollama_model]
            elif provider == "aliyun":
                targets = [self.vision_aliyun_model]
            else:
                targets = [self.vision_openai_model]
        elif mode == "ollama":
            targets = [self.ollama_chat_model]
        elif provider == "aliyun":
            targets = [self.aliyun_chat_model]
        elif provider == "openai":
            targets = [self.openai_chat_model]
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
        if (
            settings.requires_api_key()
            or settings.requires_vision_api_key()
        ):
            QMessageBox.warning(
                self,
                self._text("missing_key"),
                self._text("missing_key_body"),
            )
            return
        if settings.tts.enabled and settings.tts.uses_autodl():
            has_password = bool(
                self.tts_autodl_password.text()
                or settings.tts.autodl_password_encrypted
            )
            if not all(
                (
                    settings.tts.autodl_ssh_command.strip(),
                    settings.tts.autodl_remote_command.strip(),
                    settings.tts.autodl_remote_reference_root.strip(),
                    has_password,
                )
            ):
                QMessageBox.warning(
                    self,
                    self._text("invalid_settings"),
                    self._text("tts_autodl_missing"),
                )
                return
            if self.tts_autodl_password.text():
                try:
                    settings.tts.autodl_password_encrypted = (
                        self._platform_runtime.credentials.protect(
                            self.tts_autodl_password.text()
                        )
                    )
                except CredentialError as exc:
                    QMessageBox.warning(
                        self,
                        self._text("invalid_settings"),
                        self._text(
                            "tts_password_store_failed",
                            message=exc,
                        ),
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
        self._closing = True
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
