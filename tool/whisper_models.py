from __future__ import annotations

import argparse
import json
from pathlib import Path

from tool.config import get_model_dir

# Keep this list available even when the optional voice dependencies have not
# been installed yet. The repository IDs mirror faster_whisper.utils._MODELS.
WHISPER_MODEL_REPOSITORIES: dict[str, str] = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "tiny": "Systran/faster-whisper-tiny",
    "base.en": "Systran/faster-whisper-base.en",
    "base": "Systran/faster-whisper-base",
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
    "medium.en": "Systran/faster-whisper-medium.en",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "distil-large-v3.5": "distil-whisper/distil-large-v3.5-ct2",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

WHISPER_MODELS = tuple(WHISPER_MODEL_REPOSITORIES)


def model_repository(model_name: str) -> str:
    """Return the Hugging Face repository used by faster-whisper."""

    normalized = model_name.strip()
    return WHISPER_MODEL_REPOSITORIES.get(normalized, normalized)


def model_page_url(model_name: str) -> str:
    """Return the browser page for a built-in name or custom repository ID."""

    repository = model_repository(model_name)
    if "/" not in repository:
        return "https://huggingface.co/Systran"
    return f"https://huggingface.co/{repository}"


def managed_whisper_dir(model_name: str) -> Path:
    repository = model_repository(model_name)
    safe_name = repository.replace("/", "--")
    return get_model_dir() / "whisper" / safe_name


def find_local_model(model_name: str) -> str | None:
    """Return the cached model path without making a network request."""

    local_path = Path(model_name).expanduser()
    if local_path.is_dir():
        return str(local_path.resolve())

    managed_path = managed_whisper_dir(model_name)
    marker = managed_path / ".aipet-download.json"
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        files = payload.get("files", [])
        if files and all(
            (managed_path / str(item["path"])).is_file()
            and (managed_path / str(item["path"])).stat().st_size
            == int(item["size"])
            for item in files
        ):
            return str(managed_path.resolve())
    except (OSError, ValueError, KeyError, TypeError):
        pass

    try:
        from faster_whisper.utils import download_model
    except ImportError:
        return None

    try:
        return str(download_model(model_name, local_files_only=True))
    except Exception:
        return None


def download_whisper_model(model_name: str) -> str:
    """Download a model through faster-whisper's normal Hugging Face cache."""

    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Install requirements-voice.txt first."
        ) from exc
    return str(download_model(model_name))


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Download a faster-whisper model."
    )
    parser.add_argument("model")
    args = parser.parse_args()
    print(download_whisper_model(args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
