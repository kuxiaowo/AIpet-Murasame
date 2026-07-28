"""Shared settings models and persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aipet.platforms import get_platform_runtime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIRECTORY_NAME = "AIpet-Murasame"


def get_user_data_dir() -> Path:
    override = os.getenv("AIPET_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    return get_platform_runtime().paths.user_data_dir(APP_DIRECTORY_NAME)


def get_config_path() -> Path:
    override = os.getenv("AIPET_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return get_user_data_dir() / "config.json"


def get_cache_dir() -> Path:
    return get_platform_runtime().paths.cache_dir(APP_DIRECTORY_NAME)


def get_model_dir() -> Path:
    override = os.getenv("AIPET_MODEL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "models"


def get_default_download_root() -> Path:
    override = os.getenv("AIPET_MODEL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_platform_runtime().paths.default_download_root(
        APP_DIRECTORY_NAME,
        PROJECT_ROOT,
    )


def default_tts_engine_root() -> str:
    return str(get_default_download_root() / "tts" / "GPT-SoVITS")


def default_tts_model_dir() -> str:
    return str(get_default_download_root() / "tts" / "Murasame_SoVITS")


def default_whisper_model_dir(model_name: str = "large-v3") -> str:
    safe_name = (
        model_name.strip()
        .replace("/", "--")
        .replace("\\", "--")
        .replace(":", "-")
        or "large-v3"
    )
    return str(get_default_download_root() / "whisper" / safe_name)


class OllamaSettings(BaseModel):
    base_url: str = Field(
        default="http://127.0.0.1:11434",
        min_length=1,
    )
    chat_model: str = Field(default="qwen3.5:9b", min_length=1)
    context_window: int = Field(default=8_192, ge=2_048, le=131_072)
    timeout_seconds: int = Field(default=180, ge=10, le=600)
    keep_alive: str = Field(default="10m", min_length=1)


class APISettings(BaseModel):
    provider: Literal["deepseek", "aliyun", "openai"] = "deepseek"
    deepseek_api_key: str = ""
    aliyun_api_key: str = ""
    openai_api_key: str = ""
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        min_length=1,
    )
    aliyun_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        min_length=1,
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        min_length=1,
    )
    deepseek_chat_model: str = Field(
        default="deepseek-v4-flash",
        min_length=1,
    )
    deepseek_thinking: bool = False
    aliyun_chat_model: str = Field(default="qwen-plus", min_length=1)
    openai_chat_model: str = Field(
        default="gpt-5.6-luna",
        min_length=1,
    )
    timeout_seconds: int = Field(default=180, ge=10, le=600)

    @model_validator(mode="after")
    def migrate_retired_deepseek_aliases(self) -> "APISettings":
        if self.deepseek_chat_model == "deepseek-chat":
            self.deepseek_chat_model = "deepseek-v4-flash"
        elif self.deepseek_chat_model == "deepseek-reasoner":
            self.deepseek_chat_model = "deepseek-v4-flash"
            self.deepseek_thinking = True
        return self

    def selected_api_key(self) -> str:
        if self.provider == "deepseek":
            return (
                os.getenv("DEEPSEEK_API_KEY") or self.deepseek_api_key
            ).strip()
        if self.provider == "aliyun":
            return (
                os.getenv("DASHSCOPE_API_KEY") or self.aliyun_api_key
            ).strip()
        return (
            os.getenv("OPENAI_API_KEY") or self.openai_api_key
        ).strip()

    def selected_base_url(self) -> str:
        if self.provider == "deepseek":
            return self.deepseek_base_url
        if self.provider == "aliyun":
            return self.aliyun_base_url
        return self.openai_base_url

    def selected_chat_model(self) -> str:
        if self.provider == "deepseek":
            return self.deepseek_chat_model
        if self.provider == "aliyun":
            return self.aliyun_chat_model
        return self.openai_chat_model


class VisionSettings(BaseModel):
    enabled: bool = False
    interval_seconds: int = Field(default=300, ge=10, le=86_400)
    provider: Literal["ollama", "aliyun", "openai"] = "ollama"
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        min_length=1,
    )
    ollama_model: str = Field(default="qwen3.5:9b", min_length=1)
    ollama_context_window: int = Field(
        default=8_192,
        ge=2_048,
        le=131_072,
    )
    ollama_keep_alive: str = Field(default="10m", min_length=1)
    aliyun_api_key: str = ""
    aliyun_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        min_length=1,
    )
    aliyun_model: str = Field(default="qwen3-vl-plus", min_length=1)
    openai_api_key: str = ""
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        min_length=1,
    )
    openai_model: str = Field(default="gpt-5.6-luna", min_length=1)
    timeout_seconds: int = Field(default=180, ge=10, le=600)

    def selected_api_key(self) -> str:
        if self.provider == "aliyun":
            return (
                os.getenv("DASHSCOPE_API_KEY") or self.aliyun_api_key
            ).strip()
        if self.provider == "openai":
            return (
                os.getenv("OPENAI_API_KEY") or self.openai_api_key
            ).strip()
        return ""

    def selected_base_url(self) -> str:
        if self.provider == "aliyun":
            return self.aliyun_base_url
        if self.provider == "openai":
            return self.openai_base_url
        return self.ollama_base_url

    def selected_model(self) -> str:
        if self.provider == "aliyun":
            return self.aliyun_model
        if self.provider == "openai":
            return self.openai_model
        return self.ollama_model


class TTSSettings(BaseModel):
    enabled: bool = False
    backend: Literal["local", "autodl"] = "local"
    base_url: str = Field(
        default="http://127.0.0.1:9880/tts",
        min_length=1,
    )
    engine_root: str = Field(default_factory=default_tts_engine_root)
    model_dir: str = Field(default_factory=default_tts_model_dir)
    autodl_ssh_command: str = ""
    autodl_remote_command: str = "bash -lc 'bash run.sh; bash'"
    autodl_remote_reference_root: str = "/root/reference_voices"
    autodl_password_encrypted: str = ""
    timeout_seconds: int = Field(default=300, ge=10, le=900)

    @model_validator(mode="after")
    def fill_default_paths(self) -> "TTSSettings":
        if not self.engine_root.strip():
            self.engine_root = default_tts_engine_root()
        if not self.model_dir.strip():
            self.model_dir = default_tts_model_dir()
        return self

    def uses_autodl(self) -> bool:
        return self.backend == "autodl"


class STTSettings(BaseModel):
    enabled: bool = False
    model: str = Field(default="large-v3", min_length=1)
    model_dir: str = Field(default_factory=default_whisper_model_dir)
    device: Literal["auto", "cuda", "cpu"] = "auto"
    input_device: str = ""

    @model_validator(mode="after")
    def fill_default_path(self) -> "STTSettings":
        if not self.model_dir.strip():
            self.model_dir = default_whisper_model_dir(self.model)
        return self


class CharacterSettings(BaseModel):
    user_name: str = Field(default="主人", min_length=1, max_length=30)
    portrait: Literal["a", "b"] = "b"
    outfit: Literal["sleepwear", "casual", "uniform", "kimono"] = "kimono"
    personality_file: str = Field(default="prompt.txt", min_length=1)


class DisplaySettings(BaseModel):
    screen_index: int = Field(default=0, ge=0)
    screen_name: str = ""
    window_x: int | None = None
    window_y: int | None = None
    portrait_screen_ratio: float = Field(default=0.8, ge=0.2, le=1.0)
    show_log_console: bool = False


class IdleSettings(BaseModel):
    do_not_disturb: bool = False
    thinking_minutes: int = Field(default=6, ge=1, le=1_440)
    away_minutes: int = Field(default=10, ge=2, le=1_440)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "IdleSettings":
        if self.away_minutes <= self.thinking_minutes:
            raise ValueError("away_minutes must be greater than thinking_minutes")
        return self


class AppSettings(BaseModel):
    ui_language: Literal["en", "zh-CN"] = "en"
    mode: Literal["ollama", "api"] = "ollama"
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    api: APISettings = Field(default_factory=APISettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    character: CharacterSettings = Field(default_factory=CharacterSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    idle: IdleSettings = Field(default_factory=IdleSettings)
    history_limit: int = Field(default=30, ge=4, le=200)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_vision_settings(cls, value):
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        raw_vision = payload.get("vision")
        if not isinstance(raw_vision, dict) or "provider" in raw_vision:
            return payload

        vision = dict(raw_vision)
        ollama = payload.get("ollama")
        api = payload.get("api")
        if isinstance(ollama, dict):
            vision.setdefault("ollama_base_url", ollama.get("base_url"))
            vision.setdefault("ollama_model", ollama.get("vision_model"))
            vision.setdefault(
                "ollama_context_window",
                ollama.get("context_window"),
            )
            vision.setdefault("ollama_keep_alive", ollama.get("keep_alive"))

        api_provider = api.get("provider") if isinstance(api, dict) else None
        if payload.get("mode") == "api" and api_provider == "aliyun":
            vision["provider"] = "aliyun"
            vision.setdefault("aliyun_api_key", api.get("aliyun_api_key"))
            vision.setdefault("aliyun_base_url", api.get("aliyun_base_url"))
            vision.setdefault("aliyun_model", api.get("aliyun_vision_model"))
            vision.setdefault("timeout_seconds", api.get("timeout_seconds"))
        else:
            vision["provider"] = "ollama"
            if isinstance(ollama, dict):
                vision.setdefault(
                    "timeout_seconds",
                    ollama.get("timeout_seconds"),
                )

        payload["vision"] = {
            key: item
            for key, item in vision.items()
            if item is not None
        }
        return payload

    @model_validator(mode="after")
    def migrate_legacy_managed_tts_paths(self) -> "AppSettings":
        legacy_root = get_platform_runtime().paths.legacy_managed_tts_root(
            APP_DIRECTORY_NAME
        )
        if legacy_root is None:
            return self

        current_root = get_model_dir() / "tts"
        migrations = (
            (
                "engine_root",
                legacy_root / "GPT-SoVITS",
                current_root / "GPT-SoVITS",
            ),
            (
                "model_dir",
                legacy_root / "Murasame_SoVITS",
                current_root / "Murasame_SoVITS",
            ),
        )
        for field_name, legacy_path, current_path in migrations:
            configured = getattr(self.tts, field_name).strip()
            if configured and _paths_equal(configured, legacy_path):
                setattr(self.tts, field_name, str(current_path))
        return self

    def personality_path(self) -> Path:
        path = Path(self.character.personality_file)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def requires_api_key(self) -> bool:
        return self.mode == "api" and not self.api.selected_api_key()

    def supports_vision(self) -> bool:
        return True

    def requires_vision_api_key(self) -> bool:
        return (
            self.vision.enabled
            and self.vision.provider != "ollama"
            and not self.vision.selected_api_key()
        )


def load_settings(path: Path | None = None) -> AppSettings:
    config_path = path or get_config_path()
    if not config_path.exists():
        return AppSettings()

    with config_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return AppSettings.model_validate(payload)


def _paths_equal(left: str | Path, right: str | Path) -> bool:
    left_normalized = os.path.normcase(
        os.path.abspath(os.path.expanduser(str(left)))
    )
    right_normalized = os.path.normcase(
        os.path.abspath(os.path.expanduser(str(right)))
    )
    return left_normalized == right_normalized


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(
            settings.model_dump(mode="json"),
            file,
            ensure_ascii=False,
            indent=2,
        )
    temporary_path.replace(config_path)
    return config_path


def settings_file_exists(path: Path | None = None) -> bool:
    return (path or get_config_path()).exists()


def load_personality(settings: AppSettings) -> str:
    path = settings.personality_path()
    if not path.exists():
        raise FileNotFoundError(f"Personality prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
