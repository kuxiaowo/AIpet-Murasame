from __future__ import annotations

from tool.whisper_models import find_local_model


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
        model = WhisperModel(
            selected_model,
            device=selected_device,
            compute_type=compute_type,
        )
        segments, _ = model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
        )
        return "".join(segment.text for segment in segments).strip()

    if device != "auto":
        return transcribe_with(device)

    try:
        return transcribe_with("cuda")
    except Exception:
        # CTranslate2 may load CUDA successfully but fail only when the lazy
        # segment iterator performs its first inference. Keep that work inside
        # the fallback boundary so the standard build remains CPU-capable.
        return transcribe_with("cpu")
