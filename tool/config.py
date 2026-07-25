from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIRECTORY_NAME = "AIpet-Murasame"


def get_user_data_dir() -> Path:
    override = os.getenv("AIPET_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home()))
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_DIRECTORY_NAME


def get_config_path() -> Path:
    override = os.getenv("AIPET_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return get_user_data_dir() / "config.json"


def get_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", get_user_data_dir()))
        return base / APP_DIRECTORY_NAME / "cache"
    return get_user_data_dir() / "cache"


def get_model_dir() -> Path:
    override = os.getenv("AIPET_MODEL_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.getenv("AIPET_DATA_DIR"):
        return get_user_data_dir() / "models"
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", get_user_data_dir()))
        return base / APP_DIRECTORY_NAME / "models"
    return get_user_data_dir() / "models"


class OllamaSettings(BaseModel):
    base_url: str = Field(
        default="http://127.0.0.1:11434",
        min_length=1,
    )
    chat_model: str = Field(default="qwen3:14b", min_length=1)
    vision_model: str = Field(default="qwen2.5vl:7b", min_length=1)
    context_window: int = Field(default=8_192, ge=2_048, le=131_072)
    timeout_seconds: int = Field(default=180, ge=10, le=600)
    keep_alive: str = Field(default="10m", min_length=1)


class APISettings(BaseModel):
    provider: Literal["deepseek", "aliyun"] = "deepseek"
    deepseek_api_key: str = ""
    aliyun_api_key: str = ""
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        min_length=1,
    )
    aliyun_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        min_length=1,
    )
    deepseek_chat_model: str = Field(
        default="deepseek-v4-flash",
        min_length=1,
    )
    deepseek_thinking: bool = False
    aliyun_chat_model: str = Field(default="qwen-plus", min_length=1)
    aliyun_vision_model: str = Field(
        default="qwen3-vl-plus",
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
        return (
            os.getenv("DASHSCOPE_API_KEY") or self.aliyun_api_key
        ).strip()

    def selected_base_url(self) -> str:
        if self.provider == "deepseek":
            return self.deepseek_base_url
        return self.aliyun_base_url

    def selected_chat_model(self) -> str:
        if self.provider == "deepseek":
            return self.deepseek_chat_model
        return self.aliyun_chat_model


class VisionSettings(BaseModel):
    enabled: bool = False
    interval_seconds: int = Field(default=300, ge=10, le=86_400)


class TTSSettings(BaseModel):
    enabled: bool = False
    base_url: str = Field(
        default="http://127.0.0.1:9880/tts",
        min_length=1,
    )
    engine_root: str = ""
    model_dir: str = ""
    timeout_seconds: int = Field(default=300, ge=10, le=900)


class STTSettings(BaseModel):
    enabled: bool = False
    model: str = Field(default="large-v3", min_length=1)
    device: Literal["auto", "cuda", "cpu"] = "auto"


class CharacterSettings(BaseModel):
    user_name: str = Field(default="主人", min_length=1, max_length=30)
    portrait: Literal["a", "b"] = "b"
    personality_file: str = Field(default="prompt.txt", min_length=1)


class DisplaySettings(BaseModel):
    screen_index: int = Field(default=0, ge=0)
    portrait_screen_ratio: float = Field(default=0.8, ge=0.2, le=1.0)


class IdleSettings(BaseModel):
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

    def personality_path(self) -> Path:
        path = Path(self.character.personality_file)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def requires_api_key(self) -> bool:
        return self.mode == "api" and not self.api.selected_api_key()

    def supports_vision(self) -> bool:
        return self.mode == "ollama" or self.api.provider == "aliyun"


def load_settings(path: Path | None = None) -> AppSettings:
    config_path = path or get_config_path()
    if not config_path.exists():
        return AppSettings()

    with config_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return AppSettings.model_validate(payload)


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
