from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from tool.runtime_logging import get_logger
from tool.whisper_models import find_local_model


logger = get_logger("voice")


@dataclass
class _CachedModel:
    model: Any
    inference_lock: threading.Lock


_MODEL_CACHE: dict[tuple[object, str, str, str], _CachedModel] = {}
_MODEL_CACHE_LOCK = threading.Lock()
_AUTO_DEVICE_CHOICES: dict[tuple[object, str], str] = {}


def _get_cached_model(
    model_class,
    model_path: str,
    device: str,
    compute_type: str,
) -> _CachedModel:
    cache_key = (model_class, model_path, device, compute_type)
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached is not None:
            return cached

        started_at = time.monotonic()
        logger.info(
            "Whisper 模型开始加载 | 设备=%s | 计算类型=%s",
            device,
            compute_type,
        )
        model = model_class(
            model_path,
            device=device,
            compute_type=compute_type,
        )
        cached = _CachedModel(
            model=model,
            inference_lock=threading.Lock(),
        )
        _MODEL_CACHE[cache_key] = cached
        logger.info(
            "Whisper 模型加载完成 | 设备=%s | 耗时=%.2f 秒",
            device,
            time.monotonic() - started_at,
        )
        return cached


def clear_model_cache() -> None:
    """Release cached Whisper models during application shutdown or tests."""

    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE.clear()
        _AUTO_DEVICE_CHOICES.clear()


def transcribe_full(
    audio_path: str,
    *,
    model_size: str = "large-v3",
    model_directory: str = "",
    device: str = "auto",
) -> str:
    """Transcribe a WAV file with the optional faster-whisper dependency."""

    from faster_whisper import WhisperModel

    selected_model = find_local_model(model_size, model_directory)
    if selected_model is None:
        raise RuntimeError(
            "Whisper model was not found in the configured model directory. "
            "Select a download directory and download the model in Settings."
        )

    def transcribe_with(selected_device: str) -> str:
        compute_type = "float16" if selected_device == "cuda" else "int8"
        cached = _get_cached_model(
            WhisperModel,
            selected_model,
            selected_device,
            compute_type,
        )
        with cached.inference_lock:
            segments, _ = cached.model.transcribe(
                audio_path,
                language="zh",
                beam_size=5,
            )
            return "".join(segment.text for segment in segments).strip()

    if device != "auto":
        return transcribe_with(device)

    auto_key = (WhisperModel, selected_model)
    with _MODEL_CACHE_LOCK:
        preferred_device = _AUTO_DEVICE_CHOICES.get(auto_key)
    if preferred_device is not None:
        return transcribe_with(preferred_device)

    try:
        result = transcribe_with("cuda")
        with _MODEL_CACHE_LOCK:
            _AUTO_DEVICE_CHOICES[auto_key] = "cuda"
        return result
    except Exception:
        # CTranslate2 may load CUDA successfully but fail only when the lazy
        # segment iterator performs its first inference. Keep that work inside
        # the fallback boundary so the standard build remains CPU-capable.
        result = transcribe_with("cpu")
        with _MODEL_CACHE_LOCK:
            _AUTO_DEVICE_CHOICES[auto_key] = "cpu"
        return result


__all__ = ["clear_model_cache", "transcribe_full"]
