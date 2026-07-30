"""Shared GPT-SoVITS asset discovery and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from aipet.core.config import get_model_dir
from aipet.core.network import is_loopback_url
from aipet.core.runtime_logging import get_logger


GPT_WEIGHT_NAME = "murasame-gpt.ckpt"
SOVITS_WEIGHT_NAME = "murasame-sovits.pth"
MIN_GPT_WEIGHT_SIZE = 100_000_000
MIN_SOVITS_WEIGHT_SIZE = 50_000_000
logger = get_logger("tts-assets")


def managed_tts_model_dir() -> Path:
    return (
        get_model_dir()
        / "tts"
        / "Murasame_SoVITS"
    )


def managed_gpt_sovits_dir() -> Path:
    return get_model_dir() / "tts" / "GPT-SoVITS"


@dataclass(frozen=True)
class TTSAssetState:
    engine_root: Path | None
    engine_ready: bool
    gpt_weight: Path | None
    sovits_weight: Path | None
    reference_root: Path | None
    reference_voices_ready: bool

    @property
    def model_ready(self) -> bool:
        return self.gpt_weight is not None and self.sovits_weight is not None

    @property
    def model_directory(self) -> Path | None:
        if not self.model_ready:
            return None
        if self.gpt_weight.parent == self.sovits_weight.parent:
            return self.gpt_weight.parent
        return None


def locate_tts_assets(
    *,
    configured_engine_root: str = "",
    configured_model_dir: str = "",
) -> TTSAssetState:
    engine_root = locate_gpt_sovits_root(configured_engine_root)
    gpt_weight, sovits_weight = locate_murasame_weights(
        configured_model_dir=configured_model_dir,
    )
    reference_root = locate_reference_voices(configured_model_dir)
    return TTSAssetState(
        engine_root=engine_root,
        engine_ready=_engine_assets_are_ready(engine_root),
        gpt_weight=gpt_weight,
        sovits_weight=sovits_weight,
        reference_root=reference_root,
        reference_voices_ready=reference_root is not None,
    )


def locate_gpt_sovits_root(configured: str = "") -> Path | None:
    candidate = (
        Path(configured).expanduser()
        if configured.strip()
        else managed_gpt_sovits_dir()
    )
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if (resolved / "api_v2.py").is_file():
        return resolved
    return None


def locate_murasame_weights(
    *,
    configured_model_dir: str = "",
) -> tuple[Path | None, Path | None]:
    directory = (
        Path(configured_model_dir).expanduser()
        if configured_model_dir.strip()
        else managed_tts_model_dir()
    )
    return (
        _valid_weight(directory / GPT_WEIGHT_NAME, MIN_GPT_WEIGHT_SIZE),
        _valid_weight(
            directory / SOVITS_WEIGHT_NAME,
            MIN_SOVITS_WEIGHT_SIZE,
        ),
    )


def tts_service_is_reachable(base_url: str, timeout: float = 1.0) -> bool:
    """Return whether *base_url* exposes a verifiable POST /tts API.

    A generic 4xx response only proves that a TCP/HTTP server owns the port.
    It does not prove that the service is GPT-SoVITS-compatible or healthy.
    """

    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    session = requests.Session()
    if is_loopback_url(base_url):
        session.trust_env = False
    schema_url = urlunsplit(
        (parsed.scheme, parsed.netloc, "/openapi.json", "", "")
    )
    try:
        response = session.get(
            schema_url,
            timeout=(timeout, timeout),
        )
        if response.status_code != 200:
            logger.debug(
                "TTS 健康检查失败 | GET %s | HTTP %s",
                schema_url,
                response.status_code,
            )
            return False
        payload = response.json()
        paths = payload.get("paths", {})
        tts_path = paths.get("/tts") if isinstance(paths, dict) else None
        reachable = isinstance(tts_path, dict) and "post" in tts_path
        if not reachable:
            logger.debug(
                "TTS 健康检查失败 | GET %s | OpenAPI 未声明 POST /tts",
                schema_url,
            )
        return reachable
    except requests.RequestException as exc:
        logger.debug(
            "TTS 健康检查连接失败 | GET %s | %s: %s",
            schema_url,
            type(exc).__name__,
            exc,
        )
        return False
    except (ValueError, AttributeError) as exc:
        logger.debug(
            "TTS 健康检查响应无效 | GET %s | %s: %s",
            schema_url,
            type(exc).__name__,
            exc,
        )
        return False


def configure_local_tts_weights(
    base_url: str,
    state: TTSAssetState,
    timeout_seconds: int,
) -> None:
    if not is_loopback_url(base_url) or not state.model_ready:
        return
    root = base_url.rstrip("/")
    if root.endswith("/tts"):
        root = root[:-4]
    session = requests.Session()
    session.trust_env = False
    for endpoint, path in (
        ("set_gpt_weights", state.gpt_weight),
        ("set_sovits_weights", state.sovits_weight),
    ):
        url = f"{root}/{endpoint}"
        try:
            response = session.get(
                url,
                params={"weights_path": str(path.resolve())},
                timeout=(5, timeout_seconds),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is None:
                logger.warning(
                    "TTS 权重加载连接失败 | GET %s | %s: %s",
                    url,
                    type(exc).__name__,
                    exc,
                )
                raise
            logger.warning(
                "TTS 权重加载请求失败 | GET %s | HTTP %s | "
                "Content-Type=%s | 响应=%s",
                url,
                response.status_code,
                response.headers.get("Content-Type", ""),
                _response_text_summary(response),
            )
            raise
        logger.info(
            "TTS 权重加载完成 | %s | HTTP %s | 权重=%s",
            endpoint,
            response.status_code,
            path,
        )


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


def _valid_weight(path: Path, minimum_size: int) -> Path | None:
    try:
        if path.is_file() and path.stat().st_size >= minimum_size:
            return path.resolve()
    except OSError:
        pass
    return None


def locate_reference_voices(configured_model_dir: str = "") -> Path | None:
    model_directory = (
        Path(configured_model_dir).expanduser()
        if configured_model_dir.strip()
        else managed_tts_model_dir()
    )
    root = model_directory / "reference_voices"
    if _reference_voices_are_ready(root):
        return root.resolve()
    return None


def _reference_voices_are_ready(root: Path) -> bool:
    for emotion in ("平静", "高兴", "害羞", "生气", "惊讶", "着急"):
        directory = root / emotion
        if not (directory / "asr.txt").is_file():
            return False
        try:
            if not any(
                item.suffix.lower() in {".wav", ".mp3", ".flac"}
                for item in directory.iterdir()
            ):
                return False
        except OSError:
            return False
    return True


def _engine_assets_are_ready(engine_root: Path | None) -> bool:
    if engine_root is None:
        return False
    required = (
        "api_v2.py",
        "GPT_SoVITS/configs/tts_infer.yaml",
        (
            "GPT_SoVITS/pretrained_models/"
            "chinese-roberta-wwm-ext-large/pytorch_model.bin"
        ),
        (
            "GPT_SoVITS/pretrained_models/"
            "chinese-hubert-base/pytorch_model.bin"
        ),
        (
            "GPT_SoVITS/pretrained_models/"
            "gsv-v4-pretrained/vocoder.pth"
        ),
    )
    return all((engine_root / relative).is_file() for relative in required)
