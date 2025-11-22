from faster_whisper import WhisperModel
from tool.config import get_config
stt_model = get_config("./config.json")["stt_model"]

def transcribe_full(audio_path: str, model_size="large-v3",device="cuda") -> str:

    # 尝试 GPU，失败自动切 CPU
    try:
        model = WhisperModel(model_size, device=device, compute_type="float16")
    except Exception:
        print("⚠ GPU 初始化失败，使用 CPU")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # 识别
    segments, info = model.transcribe(audio_path,language="zh",beam_size=5)

    # 合并成一句完整话
    full_text = "".join(seg.text for seg in segments).strip()
    return full_text
