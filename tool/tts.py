from __future__ import annotations

import uuid
from pathlib import Path

import requests

from tool.backends import Emotion
from tool.config import AppSettings, PROJECT_ROOT, get_cache_dir
from tool.network import is_loopback_url


class TTSError(RuntimeError):
    pass


class TTSClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.session = requests.Session()
        if is_loopback_url(settings.tts.base_url):
            self.session.trust_env = False

    def synthesize(self, text: str, emotion: Emotion) -> Path:
        config = self.settings.tts
        reference_dir = PROJECT_ROOT / "reference_voices" / emotion
        transcript_path = reference_dir / "asr.txt"
        audio_files = sorted(
            path
            for path in reference_dir.iterdir()
            if path.suffix.lower() in {".wav", ".mp3", ".flac"}
        )
        if not transcript_path.exists() or not audio_files:
            raise TTSError(f"缺少情绪参考语音: {emotion}")

        local_audio = audio_files[0]
        if config.remote_reference_root.strip():
            reference_path = (
                Path(config.remote_reference_root)
                / emotion
                / local_audio.name
            ).as_posix()
        else:
            reference_path = str(local_audio.resolve())

        params = {
            "text": text,
            "text_lang": "ja",
            "ref_audio_path": reference_path,
            "aux_ref_audio_paths": [],
            "prompt_text": transcript_path.read_text(encoding="utf-8").strip(),
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
