"""Whisper language-setting metadata and normalization."""

from __future__ import annotations

import re


COMMON_WHISPER_LANGUAGES: tuple[tuple[str, str, str], ...] = (
    ("zh", "Chinese", "中文"),
    ("en", "English", "英语"),
    ("ja", "Japanese", "日语"),
    ("ko", "Korean", "韩语"),
    ("es", "Spanish", "西班牙语"),
    ("fr", "French", "法语"),
    ("de", "German", "德语"),
    ("pt", "Portuguese", "葡萄牙语"),
    ("ru", "Russian", "俄语"),
    ("ar", "Arabic", "阿拉伯语"),
    ("hi", "Hindi", "印地语"),
    ("it", "Italian", "意大利语"),
    ("tr", "Turkish", "土耳其语"),
    ("pl", "Polish", "波兰语"),
    ("nl", "Dutch", "荷兰语"),
    ("id", "Indonesian", "印度尼西亚语"),
    ("vi", "Vietnamese", "越南语"),
    ("th", "Thai", "泰语"),
    ("uk", "Ukrainian", "乌克兰语"),
)

_LANGUAGE_ALIASES = {
    "zh-cn": "zh",
    "zh-sg": "zh",
    "zh-tw": "zh",
    "zh-hk": "zh",
    "en-us": "en",
    "en-gb": "en",
    "ja-jp": "ja",
    "ko-kr": "ko",
}


def normalize_stt_language(value: object) -> str:
    """Normalize a saved STT language selector or Whisper language code."""

    normalized = str(value or "").strip().lower().replace("_", "-")
    normalized = _LANGUAGE_ALIASES.get(normalized, normalized)
    if normalized in {"auto", "ui"}:
        return normalized
    if not re.fullmatch(r"[a-z]{2,3}", normalized):
        raise ValueError(
            "language must be 'auto', 'ui', or a two- or three-letter "
            "Whisper language code"
        )
    return normalized


def resolve_stt_language(
    configured_language: str,
    ui_language: str,
) -> str | None:
    """Resolve special selectors to the code expected by faster-whisper."""

    normalized = normalize_stt_language(configured_language)
    if normalized == "auto":
        return None
    if normalized == "ui":
        return "en" if ui_language == "en" else "zh"
    return normalized


__all__ = [
    "COMMON_WHISPER_LANGUAGES",
    "normalize_stt_language",
    "resolve_stt_language",
]
