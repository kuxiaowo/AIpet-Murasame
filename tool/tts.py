from __future__ import annotations

import uuid
from pathlib import Path

import requests

from tool.backends import Emotion
from tool.config import AppSettings, get_cache_dir
from tool.network import is_loopback_url
from tool.tts_assets import configure_local_tts_weights, locate_tts_assets
from tool.tts_service import TTSServiceError, get_tts_service_manager


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
        config = self.settings.tts
        if config.uses_autodl():
            manager = get_tts_service_manager()
            try:
                manager.ensure_running(config)
                reference_audio_path, prompt_text = (
                    manager.autodl_reference(config, emotion)
                )
            except TTSServiceError as exc:
                raise TTSError(f"AutoDL TTS 启动失败: {exc}") from exc
        else:
            state = locate_tts_assets(
                configured_engine_root=config.engine_root,
                configured_model_dir=config.model_dir,
            )
            if not state.model_ready:
                raise TTSError("丛雨 TTS 模型尚未下载完成")
            try:
                get_tts_service_manager().ensure_running(
                    config,
                    state=state,
                )
            except TTSServiceError as exc:
                raise TTSError(f"TTS 服务启动失败: {exc}") from exc

            try:
                if not self._weights_configured:
                    configure_local_tts_weights(
                        config.base_url,
                        state,
                        config.timeout_seconds,
                    )
                    self._weights_configured = True
            except requests.RequestException as exc:
                raise TTSError(f"TTS 模型加载失败: {exc}") from exc

            if state.reference_root is None:
                raise TTSError("丛雨 TTS 参考音频尚未下载完成")
            reference_dir = state.reference_root / emotion
            transcript_path = reference_dir / "asr.txt"
            audio_files = sorted(
                path
                for path in reference_dir.iterdir()
                if path.suffix.lower() in {".wav", ".mp3", ".flac"}
            )
            if not transcript_path.exists() or not audio_files:
                raise TTSError(f"缺少情绪参考语音: {emotion}")
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

        try:
            response = self.session.post(
                config.base_url,
                json=params,
                timeout=(10, config.timeout_seconds),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TTSError(f"TTS 请求失败: {exc}") from exc

        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("audio/"):
            detail = response.text[:500]
            raise TTSError(f"TTS 未返回音频: {detail}")

        output_dir = get_cache_dir() / "voices"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uuid.uuid4().hex}.wav"
        output_path.write_bytes(response.content)
        return output_path
