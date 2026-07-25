from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from tool.backends import CharacterReply, create_backend
from tool.config import AppSettings
from tool.tts import TTSClient, TTSError


@dataclass(frozen=True)
class ConversationResult:
    reply: CharacterReply
    audio_paths: list[Path | None]
    user_text: str
    is_user_message: bool


class ConversationWorker(QThread):
    """Run model and TTS requests without blocking the Qt event loop."""

    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(
        self,
        settings: AppSettings,
        history: list[dict[str, str]],
        user_text: str,
        *,
        event_context: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.history = history
        self.user_text = user_text
        self.event_context = event_context
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            backend = create_backend(self.settings)
            reply = backend.chat(
                self.history,
                self.user_text,
                self.event_context,
            )
            if self._cancelled.is_set():
                return

            audio_paths: list[Path | None] = [None] * len(reply.sentences)
            if self.settings.tts.enabled:
                tts = TTSClient(self.settings)
                for index, sentence in enumerate(reply.sentences):
                    if self._cancelled.is_set():
                        self._remove_audio(audio_paths)
                        return
                    try:
                        audio_paths[index] = tts.synthesize(
                            sentence.ja,
                            sentence.emotion,
                        )
                    except TTSError as exc:
                        self.warning.emit(str(exc))

            if self._cancelled.is_set():
                self._remove_audio(audio_paths)
                return

            self.result_ready.emit(
                ConversationResult(
                    reply=reply,
                    audio_paths=audio_paths,
                    user_text=self.user_text,
                    is_user_message=self.event_context is None,
                )
            )
        except Exception as exc:
            if not self._cancelled.is_set():
                self.error.emit(str(exc))

    @staticmethod
    def _remove_audio(audio_paths: list[Path | None]) -> None:
        for path in audio_paths:
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


class VisionWorker(QThread):
    """Analyze a screenshot using the configured vision model."""

    description_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        settings: AppSettings,
        image_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.image_path = image_path
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            description = create_backend(self.settings).describe_image(
                self.image_path
            )
            if not self._cancelled.is_set() and description:
                self.description_ready.emit(description)
        except Exception as exc:
            if not self._cancelled.is_set():
                self.error.emit(str(exc))
        finally:
            try:
                self.image_path.unlink(missing_ok=True)
            except OSError:
                pass
