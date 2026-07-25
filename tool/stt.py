from __future__ import annotations

from tool.whisper_models import find_local_model


def transcribe_full(
    audio_path: str,
    *,
    model_size: str = "large-v3",
    device: str = "auto",
) -> str:
    """Transcribe a WAV file with the optional faster-whisper dependency."""

    from faster_whisper import WhisperModel

    selected_model = find_local_model(model_size) or model_size
    selected_device = device
    if selected_device == "auto":
        selected_device = "cuda"

    compute_type = "float16" if selected_device == "cuda" else "int8"
    try:
        model = WhisperModel(
            selected_model,
            device=selected_device,
            compute_type=compute_type,
        )
    except Exception:
        if device != "auto":
            raise
        model = WhisperModel(
            selected_model,
            device="cpu",
            compute_type="int8",
        )

    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
    )
    return "".join(segment.text for segment in segments).strip()
