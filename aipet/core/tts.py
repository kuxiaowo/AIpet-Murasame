"""Shared text-to-speech client."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import requests

from aipet.core.backends import Emotion
from aipet.core.config import AppSettings, get_cache_dir
from aipet.core.network import is_loopback_url
from aipet.core.runtime_logging import get_logger
from aipet.core.tts_assets import configure_local_tts_weights, locate_tts_assets
from aipet.core.tts_service import TTSServiceError, get_tts_service_manager


logger = get_logger("tts")


class TTSError(RuntimeError):
    pass


class TTSClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.session = requests.Session()
        if is_loopback_url(settings.tts.base_url):
            self.session.trust_env = False
        self._weights_configured = False

    def synthesize(self, text: str, emotion: Emotion) -> Path:
        request_id = uuid.uuid4().hex[:8]
        config = self.settings.tts
        logger.info(
            "TTS 合成准备 | ID=%s | 后端=%s | 地址=%s | "
            "文本字符=%s | 文本预览=%s | 情绪=%s",
            request_id,
            config.backend,
            config.base_url,
            len(text),
            _text_preview(text),
            emotion,
        )
        if config.uses_autodl():
            manager = get_tts_service_manager()
            try:
                manager.ensure_running(config)
                reference_audio_path, prompt_text = (
                    manager.autodl_reference(config, emotion)
                )
            except TTSServiceError as exc:
                raise TTSError(
                    f"AutoDL TTS 启动失败 [ID={request_id}]: {exc}"
                ) from exc
        else:
            state = locate_tts_assets(
                configured_engine_root=config.engine_root,
                configured_model_dir=config.model_dir,
            )
            logger.info(
                "TTS 本地资源检查 | ID=%s | 配置引擎=%s | "
                "定位引擎=%s | 引擎就绪=%s | 配置模型=%s | "
                "GPT权重=%s | SoVITS权重=%s | 参考音频=%s | "
                "参考音频就绪=%s",
                request_id,
                config.engine_root,
                state.engine_root,
                state.engine_ready,
                config.model_dir,
                state.gpt_weight,
                state.sovits_weight,
                state.reference_root,
                state.reference_voices_ready,
            )
            if not state.model_ready:
                raise TTSError(
                    f"丛雨 TTS 模型尚未下载完成 [ID={request_id}]"
                )
            try:
                get_tts_service_manager().ensure_running(
                    config,
                    state=state,
                )
            except TTSServiceError as exc:
                raise TTSError(
                    f"TTS 服务启动失败 [ID={request_id}]: {exc}"
                ) from exc

            try:
                if not self._weights_configured:
                    configure_local_tts_weights(
                        config.base_url,
                        state,
                        config.timeout_seconds,
                    )
                    self._weights_configured = True
            except requests.RequestException as exc:
                raise TTSError(
                    f"TTS 模型加载失败 [ID={request_id}]: {exc}"
                ) from exc

            if state.reference_root is None:
                raise TTSError(
                    f"丛雨 TTS 参考音频尚未下载完成 [ID={request_id}]"
                )
            reference_dir = state.reference_root / emotion
            transcript_path = reference_dir / "asr.txt"
            audio_files = sorted(
                path
                for path in reference_dir.iterdir()
                if path.suffix.lower() in {".wav", ".mp3", ".flac"}
            )
            if not transcript_path.exists() or not audio_files:
                raise TTSError(
                    f"缺少情绪参考语音 [ID={request_id}]: {emotion}"
                )
            reference_audio_path = str(audio_files[0].resolve())
            prompt_text = transcript_path.read_text(
                encoding="utf-8"
            ).strip()

        params = {
            "text": text,
            "text_lang": "ja",
            "ref_audio_path": reference_audio_path,
            "aux_ref_audio_paths": [],
            "prompt_text": prompt_text,
            "prompt_lang": "ja",
            "top_k": 15,
            "top_p": 1,
            "temperature": 1,
            "text_split_method": "cut1",
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": True,
            "speed_factor": 1.0,
            "streaming_mode": False,
            "seed": -1,
            "parallel_infer": True,
            "repetition_penalty": 1.35,
            "sample_steps": 32,
            "super_sampling": False,
        }

        logger.info(
            "TTS 合成请求发出 | ID=%s | POST %s | 后端=%s | "
            "文本字符=%s | 文本预览=%s | 情绪=%s | 参考音频=%s | "
            "text_lang=ja | prompt_lang=ja | split=cut1 | "
            "sample_steps=32",
            request_id,
            config.base_url,
            config.backend,
            len(text),
            _text_preview(text),
            emotion,
            reference_audio_path,
        )
        started_at = time.monotonic()
        try:
            response = self.session.post(
                config.base_url,
                json=params,
                timeout=(10, config.timeout_seconds),
            )
        except requests.RequestException as exc:
            elapsed_ms = (time.monotonic() - started_at) * 1_000
            logger.warning(
                "TTS 合成请求连接失败 | ID=%s | POST %s | %.0f ms | "
                "%s: %s",
                request_id,
                config.base_url,
                elapsed_ms,
                type(exc).__name__,
                exc,
            )
            raise TTSError(
                f"TTS 请求失败 [ID={request_id}]: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        elapsed_ms = (time.monotonic() - started_at) * 1_000
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = _response_text_summary(response)
            content_type = response.headers.get("Content-Type", "")
            logger.warning(
                "TTS 合成请求被拒绝 | ID=%s | POST %s | HTTP %s | "
                "%.0f ms | Content-Type=%s | 响应=%s | 服务日志=%s",
                request_id,
                config.base_url,
                response.status_code,
                elapsed_ms,
                content_type,
                detail,
                _service_log_hint(config.uses_autodl()),
            )
            raise TTSError(
                f"TTS 请求失败 [ID={request_id}]: "
                f"HTTP {response.status_code}; "
                f"服务端响应: {detail}"
            ) from exc

        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("audio/"):
            detail = _response_text_summary(response)
            logger.warning(
                "TTS 合成响应格式异常 | ID=%s | POST %s | HTTP %s | "
                "%.0f ms | Content-Type=%s | 响应=%s",
                request_id,
                config.base_url,
                response.status_code,
                elapsed_ms,
                content_type,
                detail,
            )
            raise TTSError(
                f"TTS 未返回音频 [ID={request_id}]: {detail}"
            )

        output_dir = get_cache_dir() / "voices"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uuid.uuid4().hex}.wav"
        output_path.write_bytes(response.content)
        logger.info(
            "TTS 合成完成 | ID=%s | POST %s | HTTP %s | %.0f ms | "
            "音频=%s 字节 | 文件=%s",
            request_id,
            config.base_url,
            response.status_code,
            elapsed_ms,
            len(response.content),
            output_path,
        )
        return output_path


def _text_preview(text: str, limit: int = 80) -> str:
    normalized = " ".join(text.split())
    if len(normalized) > limit:
        normalized = normalized[:limit] + "…"
    return repr(normalized)


def _service_log_hint(uses_autodl: bool) -> str:
    if uses_autodl:
        return "<AutoDL 远端 GPT-SoVITS 日志>"
    return str(get_cache_dir() / "logs" / "gpt-sovits-service.log")


def _response_text_summary(
    response: requests.Response,
    limit: int = 2_000,
) -> str:
    content_type = response.headers.get("Content-Type", "")
    if content_type.lower().startswith("audio/"):
        return f"<音频响应已省略，{len(response.content)} 字节>"
    try:
        text = " ".join(response.text.split())
    except Exception:
        return "<响应正文无法解码>"
    if not text:
        return "<空响应>"
    if len(text) > limit:
        return text[:limit] + f"…<已截断 {len(text) - limit} 字符>"
    return text
