from __future__ import annotations


def transcribe_full(
    audio_path: str,
    *,
    model_size: str = "large-v3",
    device: str = "auto",
) -> str:
    """Transcribe a WAV file with the optional faster-whisper dependency."""

    from faster_whisper import WhisperModel

    selected_device = device
    if selected_device == "auto":
        selected_device = "cuda"

    compute_type = "float16" if selected_device == "cuda" else "int8"
    try:
        model = WhisperModel(
            model_size,
            device=selected_device,
            compute_type=compute_type,
        )
    except Exception:
        if device != "auto":
            raise
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        beam_size=5,
    )
    return "".join(segment.text for segment in segments).strip()
