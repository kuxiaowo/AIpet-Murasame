"""Shared background workers."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from aipet.core.backends import (
    CharacterReply,
    ScreenAnalysis,
    create_backend,
    create_vision_backend,
)
from aipet.core.config import AppSettings
from aipet.core.runtime_logging import get_logger, log_event
from aipet.core.tts import TTSClient, TTSError


logger = get_logger("worker")


@dataclass(frozen=True)
class ConversationResult:
    reply: CharacterReply
    audio_paths: list[Path | None]
    user_text: str
    is_user_message: bool
    user_source: str = "typed"


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
        screen_memory: str | None = None,
        user_source: str = "typed",
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.history = history
        self.user_text = user_text
        self.event_context = event_context
        self.screen_memory = screen_memory
        self.user_source = user_source
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            log_event(
                logger,
                "conversation.started",
                backend=self.settings.mode,
                source=(
                    "proactive_event"
                    if self.event_context is not None
                    else self.user_source
                ),
                history_messages=len(self.history),
                tts_enabled=self.settings.tts.enabled,
            )
            backend = create_backend(self.settings)
            reply = backend.chat(
                self.history,
                self.user_text,
                self.event_context,
                self.screen_memory,
                self.user_source,
            )
            if self._cancelled.is_set():
                log_event(logger, "conversation.cancelled")
                return

            audio_paths: list[Path | None] = [None] * len(reply.sentences)
            if self.settings.tts.enabled:
                tts = TTSClient(self.settings)
                for index, sentence in enumerate(reply.sentences):
                    if self._cancelled.is_set():
                        self._remove_audio(audio_paths)
                        log_event(logger, "conversation.cancelled")
                        return
                    try:
                        audio_paths[index] = tts.synthesize(
                            sentence.ja,
                            sentence.emotion,
                        )
                    except TTSError as exc:
                        logger.warning("TTS 合成失败：%s", exc)
                        self.warning.emit(str(exc))

            if self._cancelled.is_set():
                self._remove_audio(audio_paths)
                log_event(logger, "conversation.cancelled")
                return

            self.result_ready.emit(
                ConversationResult(
                    reply=reply,
                    audio_paths=audio_paths,
                    user_text=self.user_text,
                    is_user_message=self.event_context is None,
                    user_source=self.user_source,
                )
            )
            log_event(
                logger,
                "conversation.completed",
                sentence_count=len(reply.sentences),
                outfit=reply.outfit or self.settings.character.outfit,
                emotions=[
                    sentence.emotion for sentence in reply.sentences
                ],
                audio_count=sum(path is not None for path in audio_paths),
            )
        except Exception as exc:
            if not self._cancelled.is_set():
                logger.exception("对话任务失败")
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

    analysis_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        settings: AppSettings,
        image_path: Path,
        previous_analysis: ScreenAnalysis | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.settings = settings
        self.image_path = image_path
        self.previous_analysis = previous_analysis
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            log_event(
                logger,
                "vision.started",
                backend=self.settings.vision.provider,
                has_previous_analysis=self.previous_analysis is not None,
            )
            analysis = create_vision_backend(self.settings).describe_image(
                self.image_path,
                self.previous_analysis,
            )
            if not self._cancelled.is_set():
                self.analysis_ready.emit(analysis)
                log_event(
                    logger,
                    "vision.completed",
                    **analysis.model_dump(mode="json"),
                )
            else:
                log_event(logger, "vision.cancelled")
        except Exception as exc:
            if not self._cancelled.is_set():
                logger.exception("屏幕视觉分析失败")
                self.error.emit(str(exc))
        finally:
            try:
                self.image_path.unlink(missing_ok=True)
            except OSError:
                pass
