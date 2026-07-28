"""Shared audio-device discovery and selection."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from aipet.platforms import get_platform_runtime


_AUDIO_BACKEND_LOCK = threading.RLock()
_AUDIO_CAPTURE_ACTIVE = False


@dataclass(frozen=True)
class AudioInputDevice:
    index: int
    name: str
    hostapi: str
    max_input_channels: int

    @property
    def identifier(self) -> str:
        return encode_audio_input_device(self.name, self.hostapi)

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.hostapi}"


def encode_audio_input_device(name: str, hostapi: str) -> str:
    if not name.strip():
        return ""
    return json.dumps(
        {"name": name.strip(), "hostapi": hostapi.strip()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def decode_audio_input_device(identifier: str) -> tuple[str, str]:
    if not identifier.strip():
        return "", ""
    try:
        payload = json.loads(identifier)
    except (json.JSONDecodeError, TypeError):
        return identifier.strip(), ""
    if not isinstance(payload, dict):
        return identifier.strip(), ""
    name = payload.get("name", "")
    hostapi = payload.get("hostapi", "")
    return (
        name.strip() if isinstance(name, str) else "",
        hostapi.strip() if isinstance(hostapi, str) else "",
    )


def list_audio_input_devices() -> list[AudioInputDevice]:
    return _preferred_audio_input_devices(
        _all_compatible_audio_input_devices()
    )


def _all_compatible_audio_input_devices() -> list[AudioInputDevice]:
    try:
        import sounddevice as sd
    except ImportError:
        return []

    with _AUDIO_BACKEND_LOCK:
        return _compatible_audio_input_devices(sd)


def _compatible_audio_input_devices(sd) -> list[AudioInputDevice]:
    devices: list[AudioInputDevice] = []
    try:
        for index, raw in enumerate(sd.query_devices()):
            channels = int(raw["max_input_channels"])
            if channels <= 0:
                continue
            try:
                sd.check_input_settings(
                    device=index,
                    channels=1,
                    dtype="int16",
                    samplerate=16000,
                )
            except Exception:
                continue
            hostapi = sd.query_hostapis(int(raw["hostapi"]))
            devices.append(
                AudioInputDevice(
                    index=index,
                    name=str(raw["name"]),
                    hostapi=str(hostapi["name"]),
                    max_input_channels=channels,
                )
            )
    except Exception:
        return []
    return devices


def _preferred_audio_input_devices(
    devices: list[AudioInputDevice],
) -> list[AudioInputDevice]:
    return get_platform_runtime().audio.prepare_input_devices(
        devices
    )


def default_audio_input_device() -> AudioInputDevice | None:
    try:
        import sounddevice as sd

        with _AUDIO_BACKEND_LOCK:
            return _default_audio_input_device(sd)
    except (ImportError, TypeError, ValueError):
        return None
    except Exception:
        return None


def _default_audio_input_device(sd) -> AudioInputDevice | None:
    try:
        raw = sd.query_devices(kind="input")
        hostapi = sd.query_hostapis(int(raw["hostapi"]))
        default_index = int(sd.default.device[0])
        return AudioInputDevice(
            index=default_index,
            name=str(raw["name"]),
            hostapi=str(hostapi["name"]),
            max_input_channels=int(raw["max_input_channels"]),
        )
    except (ImportError, TypeError, ValueError):
        return None
    except Exception:
        return None


def refresh_audio_input_devices(
) -> tuple[AudioInputDevice | None, list[AudioInputDevice]]:
    """Refresh PortAudio when safe, then return the current input devices."""

    try:
        import sounddevice as sd
    except ImportError:
        return None, []

    with _AUDIO_BACKEND_LOCK:
        if not _AUDIO_CAPTURE_ACTIVE:
            _restart_portaudio(sd)
        devices = _preferred_audio_input_devices(
            _compatible_audio_input_devices(sd)
        )
        return _default_audio_input_device(sd), devices


def _restart_portaudio(sd) -> None:
    try:
        if getattr(sd, "_initialized", 0) > 0:
            sd._terminate()
        sd._initialize()
    except Exception:
        # A failed refresh must not make the existing settings window unusable.
        if getattr(sd, "_initialized", 0) <= 0:
            try:
                sd._initialize()
            except Exception:
                pass


@contextmanager
def audio_backend_access():
    """Prevent PortAudio refresh while a stream is being opened or closed."""

    with _AUDIO_BACKEND_LOCK:
        yield


def set_audio_capture_active(active: bool) -> None:
    global _AUDIO_CAPTURE_ACTIVE
    with _AUDIO_BACKEND_LOCK:
        _AUDIO_CAPTURE_ACTIVE = active


def resolve_audio_input_device(identifier: str) -> int | None:
    if not identifier.strip():
        return None

    name, hostapi = decode_audio_input_device(identifier)
    candidates = [
        device
        for device in _all_compatible_audio_input_devices()
        if device.name == name
    ]
    exact = [
        device
        for device in candidates
        if not hostapi or device.hostapi == hostapi
    ]
    if exact:
        return exact[0].index
    if len(candidates) == 1:
        return candidates[0].index

    description = f"{name} — {hostapi}" if hostapi else name
    raise RuntimeError(f"配置的录音设备当前不可用：{description}")


__all__ = [
    "AudioInputDevice",
    "audio_backend_access",
    "decode_audio_input_device",
    "default_audio_input_device",
    "encode_audio_input_device",
    "list_audio_input_devices",
    "refresh_audio_input_devices",
    "resolve_audio_input_device",
    "set_audio_capture_active",
]
