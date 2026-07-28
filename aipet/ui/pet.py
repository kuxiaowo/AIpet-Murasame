"""Shared Qt desktop-pet widget."""

from __future__ import annotations

import textwrap
import time
import uuid
import wave
from pathlib import Path

import cv2
from PyQt5.QtCore import QEvent, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QPainter,
    QPixmap,
    QScreen,
)
from PyQt5.QtMultimedia import QSound
from PyQt5.QtWidgets import QLabel

from aipet.core.workers import (
    ConversationResult,
    ConversationWorker,
    VisionWorker,
)
from aipet.core.backends import ScreenAnalysis
from aipet.core.config import AppSettings, PROJECT_ROOT, get_cache_dir
from aipet.core.generate import generate_fgimage
from aipet.core.portraits import default_layers, layers_for
from aipet.core.runtime_logging import get_logger
from aipet.core.storage import HistoryStore, ScreenMemoryEntry, ScreenMemoryStore
from aipet.core.time_utils import build_time_context
from aipet.platforms import PlatformRuntime, get_platform_runtime


SCREEN_PIXEL_CHANGE_THRESHOLD = 0.008
PROACTIVE_COOLDOWN_SECONDS = 180
TOPMOST_WATCHDOG_INTERVAL_MS = 2_000
logger = get_logger("window")


def wrap_text(text: str, width: int = 10) -> str:
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )


def get_idle_seconds(runtime: PlatformRuntime | None = None) -> float:
    """Compatibility hook delegating idle detection to the active platform."""

    return (runtime or get_platform_runtime()).input.idle_seconds()


def native_topmost_available(
    runtime: PlatformRuntime | None = None,
) -> bool:
    """Compatibility hook delegating capability checks to the platform."""

    return (runtime or get_platform_runtime()).windowing.topmost_available()


def ensure_window_topmost(
    window_id: int,
    runtime: PlatformRuntime | None = None,
) -> bool:
    """Compatibility hook delegating native window work to the platform."""

    return (runtime or get_platform_runtime()).windowing.ensure_topmost(
        window_id
    )


class Murasame(QLabel):
    notification = pyqtSignal(str, str)

    def __init__(
        self,
        settings: AppSettings,
        platform_runtime: PlatformRuntime | None = None,
    ):
        super().__init__()
        self._platform_runtime = platform_runtime or get_platform_runtime()
        self.settings = settings.model_copy(deep=True)
        self.pet_name = "丛雨"

        self.full_text = ""
        self.display_text = ""
        self.typing_prefix = ""
        self.typing_index = 0
        self.typing_timer = QTimer(self)
        self.typing_timer.setInterval(40)
        self.typing_timer.timeout.connect(self._typing_step)
        self.thinking_timer = QTimer(self)
        self.thinking_timer.setInterval(350)
        self.thinking_timer.timeout.connect(self._thinking_step)
        self._thinking_dot_count = 0

        self.input_mode = False
        self.input_buffer = ""
        self.preedit_text = ""
        self.touch_head = False
        self.head_press_x: int | None = None
        self.drag_offset = None

        self._base_font_size = 40
        self._base_text_x_offset = 140
        self._base_text_y_offset = -100
        self._base_border_size = 2
        self._current_scale = 1.0
        self._source_portrait_pixmap: QPixmap | None = None
        self._active_screen_key: tuple[object, ...] | None = None
        self._font_family = self._load_font()
        self._update_text_scaling()
        self._screen_resize_timer = QTimer(self)
        self._screen_resize_timer.setSingleShot(True)
        self._screen_resize_timer.setInterval(120)
        self._screen_resize_timer.timeout.connect(
            self._adapt_to_current_screen
        )
        self._topmost_error_logged = False
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(TOPMOST_WATCHDOG_INTERVAL_MS)
        self._topmost_timer.timeout.connect(self._ensure_topmost)

        self.history_store = HistoryStore(limit=self.settings.history_limit)
        self.history = self.history_store.load()
        self.screen_memory_store = ScreenMemoryStore()
        self._generation = 0
        self._workers: dict[int, ConversationWorker] = {}
        self._vision_worker: VisionWorker | None = None
        self._last_screen_thumbnail = None
        self._last_screen_analysis: ScreenAnalysis | None = None
        self._screen_baseline_ready = False
        self._last_spoken_screen_event = ""
        self._proactive_cooldown_until = 0.0
        self._playback_result: ConversationResult | None = None
        self._playback_index = 0
        self._sound: QSound | None = None
        self.playback_timer = QTimer(self)
        self.playback_timer.setSingleShot(True)
        self.playback_timer.timeout.connect(self._play_next_sentence)

        self._dnd_enabled = self.settings.idle.do_not_disturb
        self.idle_thinking_triggered = False
        self.idle_away_triggered = False
        self.away_trigger_time: float | None = None
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(1000)
        self.idle_timer.timeout.connect(self.check_idle_state)
        self.idle_timer.start()

        self.screenshot_timer = QTimer(self)
        self.screenshot_timer.timeout.connect(self._capture_screen)

        self._platform_runtime.windowing.configure_widget(self)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setMouseTracking(True)

        self.update_portrait(
            default_layers(
                self.settings.character.portrait,
                self.settings.character.outfit,
            ),
            self.settings.character.portrait,
            self.settings.character.outfit,
        )
        self._apply_automatic_behavior_settings()

    def _load_font(self) -> str:
        font_path = PROJECT_ROOT / "思源黑体Bold.otf"
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        return families[0] if families else QFont().family()

    def apply_settings(self, settings: AppSettings) -> None:
        old_portrait = self.settings.character.portrait
        old_outfit = self.settings.character.outfit
        was_dnd_enabled = self._dnd_enabled
        current_layers = getattr(
            self,
            "_current_layers",
            default_layers(old_portrait),
        )
        current_portrait = getattr(self, "_current_portrait", old_portrait)
        current_outfit = getattr(self, "_current_outfit", old_outfit)
        self.settings = settings.model_copy(deep=True)
        self._dnd_enabled = self.settings.idle.do_not_disturb
        if self._dnd_enabled:
            self._cancel_active_jobs()
        elif was_dnd_enabled:
            self._reset_screen_observation()
        self.history_store.limit = self.settings.history_limit
        self.history = self.history[-self.settings.history_limit :]
        self.history_store.save(self.history)
        self._reset_screen_observation()

        if (
            old_portrait != self.settings.character.portrait
            or old_outfit != self.settings.character.outfit
        ):
            portrait = self.settings.character.portrait
            outfit = self.settings.character.outfit
            self.update_portrait(
                default_layers(portrait, outfit),
                portrait,
                outfit,
            )
        else:
            self.update_portrait(
                current_layers,
                current_portrait,
                current_outfit,
            )
        self._reset_idle_state()
        self._apply_automatic_behavior_settings()

    def _apply_automatic_behavior_settings(self) -> None:
        self.screenshot_timer.stop()
        if (
            self.settings.vision.enabled
            and self.settings.supports_vision()
            and not self._dnd_enabled
        ):
            self.screenshot_timer.start(
                self.settings.vision.interval_seconds * 1000
            )
        if self._dnd_enabled:
            self.idle_timer.stop()
        elif not self.idle_timer.isActive():
            self.idle_timer.start()

    def set_screenshot_enabled(self, enabled: bool) -> None:
        if enabled and not self.settings.supports_vision():
            self.settings.vision.enabled = False
            self.notification.emit(
                "Screen vision unavailable",
                "DeepSeek mode is chat-only. Choose Alibaba Cloud or Ollama.",
            )
            return
        if bool(enabled) != self.settings.vision.enabled:
            self._reset_screen_observation()
        self.settings.vision.enabled = bool(enabled)
        self._apply_automatic_behavior_settings()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if native_topmost_available(self._platform_runtime):
            self._topmost_timer.start()
            QTimer.singleShot(0, self._ensure_topmost)

    def hideEvent(self, event) -> None:
        self._topmost_timer.stop()
        super().hideEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in {
            QEvent.ActivationChange,
            QEvent.WindowStateChange,
        }:
            QTimer.singleShot(0, self._ensure_topmost)

    def _ensure_topmost(self) -> None:
        if (
            not native_topmost_available(self._platform_runtime)
            or not self.isVisible()
        ):
            return
        try:
            ensure_window_topmost(
                int(self.winId()),
                self._platform_runtime,
            )
        except OSError as exc:
            if not self._topmost_error_logged:
                logger.warning("无法重新确认桌宠窗口置顶状态：%s", exc)
                self._topmost_error_logged = True
        else:
            self._topmost_error_logged = False

    def is_screenshot_enabled(self) -> bool:
        return self.settings.vision.enabled

    def set_dnd_enabled(self, enabled: bool) -> None:
        was_enabled = self._dnd_enabled
        self._dnd_enabled = bool(enabled)
        self.settings.idle.do_not_disturb = self._dnd_enabled
        if self._dnd_enabled:
            self._cancel_active_jobs()
            self._reset_idle_state()
        elif was_enabled:
            self._reset_screen_observation()
        self._apply_automatic_behavior_settings()

    def is_dnd_enabled(self) -> bool:
        return self._dnd_enabled

    def _reset_idle_state(self) -> None:
        self.idle_thinking_triggered = False
        self.idle_away_triggered = False
        self.away_trigger_time = None

    def _reset_screen_observation(self) -> None:
        self._last_screen_thumbnail = None
        self._last_screen_analysis = None
        self._screen_baseline_ready = False
        self._last_spoken_screen_event = ""

    def _try_start_proactive_event(self, event_context: str) -> bool:
        if (
            self._dnd_enabled
            or self.input_mode
            or bool(self._workers)
            or self._playback_result is not None
        ):
            return False

        now = time.monotonic()
        if now < self._proactive_cooldown_until:
            return False

        self._proactive_cooldown_until = now + PROACTIVE_COOLDOWN_SECONDS
        self.start_thread(event_context, role="system")
        return True

    def check_idle_state(self) -> None:
        if self._dnd_enabled:
            return

        thinking_seconds = self.settings.idle.thinking_minutes * 60
        away_seconds = self.settings.idle.away_minutes * 60
        idle_seconds = get_idle_seconds(self._platform_runtime)

        if (
            idle_seconds <= thinking_seconds
            and self.idle_away_triggered
            and self.away_trigger_time is not None
        ):
            if time.time() - self.away_trigger_time >= 30:
                self._try_start_proactive_event(
                    "用户刚刚回到电脑前。简短欢迎主人回来，并自然地问是否要继续刚才的事情。",
                )
            self._reset_idle_state()
            return

        if idle_seconds <= thinking_seconds:
            self.idle_thinking_triggered = False
            self.idle_away_triggered = False
            return

        if idle_seconds >= away_seconds and not self.idle_away_triggered:
            self.idle_away_triggered = True
            self.away_trigger_time = time.time()
            self._try_start_proactive_event(
                "用户已经离开电脑一段时间。轻声问主人是否还在，并提醒适当休息。",
            )
            return

        if not self.idle_thinking_triggered:
            self.idle_thinking_triggered = True
            self._try_start_proactive_event(
                "用户一段时间没有输入，可能正在思考、发呆或休息。"
                "温柔地关心一下，避免过分打扰。",
            )

    def _capture_screen(self) -> None:
        if (
            self._dnd_enabled
            or not self.settings.vision.enabled
            or (
                self._vision_worker is not None
                and self._vision_worker.isRunning()
            )
        ):
            return

        screens = QGuiApplication.screens()
        screen_index = self.settings.display.screen_index
        screen = (
            screens[screen_index]
            if 0 <= screen_index < len(screens)
            else QGuiApplication.primaryScreen()
        )
        if screen is None:
            self.notification.emit("屏幕分析", "没有找到可用显示器")
            return

        screenshot_dir = get_cache_dir() / "screens"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        image_path = screenshot_dir / f"{uuid.uuid4().hex}.png"
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            self.notification.emit("屏幕分析", "屏幕截图失败")
            return
        if not pixmap.save(str(image_path), "PNG"):
            self.notification.emit("屏幕分析", "屏幕截图失败")
            return

        thumbnail = self._load_screen_thumbnail(image_path)
        if thumbnail is not None:
            previous_thumbnail = self._last_screen_thumbnail
            self._last_screen_thumbnail = thumbnail
            if (
                previous_thumbnail is not None
                and not self._pixels_changed(
                    previous_thumbnail,
                    thumbnail,
                )
            ):
                image_path.unlink(missing_ok=True)
                return

        worker = VisionWorker(
            self.settings.model_copy(deep=True),
            image_path,
            previous_analysis=self._last_screen_analysis,
            parent=self,
        )
        self._vision_worker = worker
        worker.analysis_ready.connect(self._on_screen_analysis)
        worker.error.connect(
            lambda message: self.notification.emit("屏幕分析失败", message)
        )
        worker.finished.connect(lambda: self._finish_vision_worker(worker))
        worker.start()

    def _finish_vision_worker(self, worker: VisionWorker) -> None:
        if self._vision_worker is worker:
            self._vision_worker = None
        worker.deleteLater()

    @staticmethod
    def _load_screen_thumbnail(image_path: Path):
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return None
        return cv2.resize(image, (96, 54), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _pixels_changed(
        previous,
        current,
        threshold: float = SCREEN_PIXEL_CHANGE_THRESHOLD,
    ) -> bool:
        if previous.shape != current.shape:
            return True
        difference = cv2.absdiff(previous, current)
        return float(difference.mean()) / 255.0 >= threshold

    @staticmethod
    def _screen_event_key(analysis: ScreenAnalysis) -> str:
        parts = (
            analysis.software,
            analysis.activity,
            analysis.topic,
            analysis.change_summary,
        )
        return "|".join(" ".join(part.casefold().split()) for part in parts)

    def _on_screen_analysis(self, analysis: ScreenAnalysis) -> None:
        if self._dnd_enabled:
            return

        self._last_screen_analysis = analysis
        if not self._screen_baseline_ready:
            self._screen_baseline_ready = True
            return
        if (
            not analysis.significant_change
            or not analysis.change_summary.strip()
        ):
            return

        event_key = self._screen_event_key(analysis)
        if not event_key:
            return
        self.screen_memory_store.remember(
            ScreenMemoryEntry.now(
                software=analysis.software,
                activity=analysis.activity,
                topic=analysis.topic,
                change_summary=analysis.change_summary,
            )
        )
        if event_key == self._last_spoken_screen_event:
            return

        details = ["屏幕发生了明显变化。"]
        if analysis.software:
            details.append(f"软件：{analysis.software}")
        if analysis.activity:
            details.append(f"当前活动：{analysis.activity}")
        if analysis.topic:
            details.append(f"页面主题：{analysis.topic}")
        if analysis.change_summary:
            details.append(f"变化摘要：{analysis.change_summary}")
        details.append(f"当前时间：{build_time_context()}")
        if self._try_start_proactive_event("\n".join(details)):
            self._last_spoken_screen_event = event_key

    def start_thread(
        self,
        text: str,
        role: str = "user",
        t: bool = False,
        source: str = "typed",
    ) -> None:
        del t  # Kept for compatibility with previous call sites.
        clean_text = text.strip()
        if not clean_text:
            return

        self._cancel_active_jobs(include_vision=(role == "user"))
        self._generation += 1
        generation = self._generation
        event_context = clean_text if role == "system" else None
        screen_memory = (
            self.screen_memory_store.prompt_text()
            if self.settings.vision.enabled
            else None
        )
        worker = ConversationWorker(
            self.settings.model_copy(deep=True),
            list(self.history),
            clean_text if role == "user" else "",
            event_context=event_context,
            screen_memory=screen_memory,
            user_source=source if role == "user" else "typed",
            parent=self,
        )
        self._workers[generation] = worker
        worker.result_ready.connect(
            lambda result, current=generation: self._on_reply(current, result)
        )
        worker.error.connect(
            lambda message, current=generation: self._on_worker_error(
                current,
                message,
            )
        )
        worker.warning.connect(
            lambda message: self.notification.emit("语音合成", message)
        )
        worker.finished.connect(
            lambda current=generation, current_worker=worker: (
                self._finish_worker(current, current_worker)
            )
        )
        self._start_thinking_animation()
        worker.start()

    def _finish_worker(
        self,
        generation: int,
        worker: ConversationWorker,
    ) -> None:
        self._workers.pop(generation, None)
        worker.deleteLater()

    def _on_worker_error(self, generation: int, message: str) -> None:
        if generation != self._generation:
            return
        self._stop_thinking_animation()
        self.show_text("连接失败，请检查模型设置。", typing=False)
        self.notification.emit("模型请求失败", message)

    def _on_reply(
        self,
        generation: int,
        result: ConversationResult,
    ) -> None:
        if generation != self._generation:
            self._remove_audio_files(result)
            return

        self._stop_thinking_animation()
        outfit = result.reply.outfit or self.settings.character.outfit
        self.settings.character.outfit = outfit
        if result.is_user_message:
            user_message = {
                "role": "user",
                "content": result.user_text,
            }
            if result.user_source == "voice":
                user_message["source"] = "voice"
            self.history.append(user_message)
        self.history.append(
            {
                "role": "assistant",
                "content": result.reply.model_dump_json(exclude_none=True),
            }
        )
        self.history = self.history[-self.settings.history_limit :]
        self.history_store.save(self.history)

        self._playback_result = result
        self._playback_index = 0
        self._play_next_sentence()

    def _play_next_sentence(self) -> None:
        result = self._playback_result
        if result is None or self._playback_index >= len(result.reply.sentences):
            if result is not None:
                self._remove_audio_files(result)
            self._playback_result = None
            self._sound = None
            return

        index = self._playback_index
        self._playback_index += 1
        sentence = result.reply.sentences[index]
        portrait = sentence.portrait or self.settings.character.portrait
        outfit = self.settings.character.outfit
        self.update_portrait(
            layers_for(portrait, sentence.emotion, outfit),
            portrait,
            outfit,
        )
        self.show_text(sentence.zh, typing=True)

        audio_path = result.audio_paths[index]
        audio_duration = self._audio_duration_milliseconds(audio_path)
        if audio_path is not None and audio_path.exists() and audio_duration > 0:
            self._sound = QSound(str(audio_path), self)
            self._sound.play()
        delay = max(40 * len(sentence.zh) + 800, audio_duration + 400)
        self.playback_timer.start(int(delay))

    @staticmethod
    def _audio_duration_milliseconds(path: Path | None) -> int:
        if path is None or not path.exists():
            return 0
        try:
            with wave.open(str(path), "rb") as audio:
                return int(audio.getnframes() / audio.getframerate() * 1000)
        except (OSError, wave.Error, ZeroDivisionError):
            return 0

    def _cancel_active_jobs(self, *, include_vision: bool = False) -> None:
        self._generation += 1
        for worker in self._workers.values():
            worker.cancel()
        if include_vision and self._vision_worker is not None:
            self._vision_worker.cancel()
        self._stop_playback()

    def _stop_playback(self) -> None:
        self.playback_timer.stop()
        self.typing_timer.stop()
        self._stop_thinking_animation()
        if self._sound is not None:
            self._sound.stop()
            self._sound = None
        if self._playback_result is not None:
            self._remove_audio_files(self._playback_result)
            self._playback_result = None

    @staticmethod
    def _remove_audio_files(result: ConversationResult) -> None:
        for path in result.audio_paths:
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def update_portrait(
        self,
        layers: list[int],
        portrait: str | None = None,
        outfit: str | None = None,
    ) -> None:
        previous_geometry = (
            self.geometry()
            if self._source_portrait_pixmap is not None
            else None
        )
        screen = (
            self._screen_at_current_position()
            if previous_geometry is not None
            else self._configured_screen()
        )
        portrait = portrait or self.settings.character.portrait
        outfit = outfit or self.settings.character.outfit
        self._current_layers = list(layers)
        self._current_portrait = portrait
        self._current_outfit = outfit
        target = f"ムラサメ{portrait}"
        bgra_image = generate_fgimage(target, layers)
        rgba_image = cv2.cvtColor(bgra_image, cv2.COLOR_BGRA2RGBA)
        height, width, channels = rgba_image.shape
        image = QImage(
            rgba_image.data,
            width,
            height,
            channels * width,
            QImage.Format_RGBA8888,
        ).copy()
        self._source_portrait_pixmap = QPixmap.fromImage(image)
        pixmap = self._scale_portrait_pixmap(
            self._source_portrait_pixmap,
            screen,
        )
        self.setPixmap(pixmap)
        self.resize(pixmap.size())
        if previous_geometry is not None and screen is not None:
            available = screen.availableGeometry()
            x = previous_geometry.center().x() - pixmap.width() // 2
            y = previous_geometry.bottom() - pixmap.height() + 1
            max_x = max(
                available.left(),
                available.right() - pixmap.width() + 1,
            )
            max_y = max(
                available.top(),
                available.bottom() - pixmap.height() + 1,
            )
            self.move(
                max(available.left(), min(x, max_x)),
                max(available.top(), min(y, max_y)),
            )
        self.update()

    def _configured_screen(self) -> QScreen | None:
        screens = QGuiApplication.screens()
        index = self.settings.display.screen_index
        return (
            screens[index]
            if 0 <= index < len(screens)
            else QGuiApplication.primaryScreen()
        )

    def _scale_portrait_pixmap(
        self,
        pixmap: QPixmap,
        screen: QScreen | None = None,
    ) -> QPixmap:
        screen = screen or self._configured_screen()
        available_height = (
            screen.availableGeometry().height() if screen is not None else 0
        )
        target_height = self._target_portrait_height(
            pixmap.height(),
            available_height,
            self.settings.display.portrait_screen_ratio,
        )
        self._current_scale = target_height / max(1, pixmap.height())
        self._active_screen_key = self._screen_key(screen)
        self._update_text_scaling()
        return pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)

    @staticmethod
    def _target_portrait_height(
        source_height: int,
        available_height: int,
        ratio: float,
    ) -> int:
        if available_height <= 0:
            return max(1, source_height)
        return max(1, int(available_height * ratio))

    @staticmethod
    def _screen_key(screen: QScreen | None) -> tuple[object, ...] | None:
        if screen is None:
            return None
        geometry = screen.availableGeometry()
        return (
            screen.name(),
            geometry.x(),
            geometry.y(),
            geometry.width(),
            geometry.height(),
        )

    def _screen_at_current_position(self) -> QScreen | None:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is not None:
            return screen
        handle = self.windowHandle()
        if handle is not None and handle.screen() is not None:
            return handle.screen()
        return self._configured_screen()

    def remember_window_position(self) -> None:
        screen = self._screen_at_current_position()
        if screen is None:
            return

        available = screen.availableGeometry()
        display = self.settings.display
        display.screen_name = screen.name()
        display.window_x = self.x() - available.x()
        display.window_y = self.y() - available.y()

        screen_key = self._screen_key(screen)
        for index, candidate in enumerate(QGuiApplication.screens()):
            if candidate is screen or self._screen_key(candidate) == screen_key:
                display.screen_index = index
                break

    def _adapt_to_current_screen(self) -> None:
        source = self._source_portrait_pixmap
        screen = self._screen_at_current_position()
        if (
            source is None
            or source.isNull()
            or screen is None
            or self._screen_key(screen) == self._active_screen_key
        ):
            return

        old_geometry = self.geometry()
        scaled = self._scale_portrait_pixmap(source, screen)
        self.setPixmap(scaled)
        self.resize(scaled.size())

        available = screen.availableGeometry()
        x = old_geometry.center().x() - scaled.width() // 2
        y = old_geometry.bottom() - scaled.height() + 1
        x = max(
            available.left(),
            min(x, available.right() - scaled.width() + 1),
        )
        y = max(
            available.top(),
            min(y, available.bottom() - scaled.height() + 1),
        )
        self.move(x, y)

        screens = QGuiApplication.screens()
        screen_key = self._screen_key(screen)
        for index, candidate in enumerate(screens):
            if candidate is screen or self._screen_key(candidate) == screen_key:
                self.settings.display.screen_index = index
                break
        self.update()

    def _update_text_scaling(self) -> None:
        scale = max(self._current_scale, 0.1)
        font_size = max(10, round(self._base_font_size * scale))
        self.text_font = QFont(self._font_family, font_size)
        self.text_x_offset = max(
            10,
            round(self._base_text_x_offset * scale),
        )
        self.text_y_offset = min(
            -10,
            round(self._base_text_y_offset * scale),
        )
        self.border_size = max(1, round(self._base_border_size * scale))

    def show_text(
        self,
        text: str,
        typing: bool = True,
        speaker_name: str | None = None,
    ) -> None:
        self._stop_thinking_animation()
        self.full_text = wrap_text(text)
        self.typing_prefix = f"【{speaker_name or self.pet_name}】\n"
        self.typing_index = 0
        self.typing_timer.stop()
        if typing:
            self.display_text = self.typing_prefix
            self.typing_timer.start()
        else:
            self.display_text = self.typing_prefix + self.full_text
            self.update()

    def _start_thinking_animation(self) -> None:
        self.typing_timer.stop()
        self._thinking_dot_count = 0
        self._thinking_step()
        self.thinking_timer.start()

    def _stop_thinking_animation(self) -> None:
        self.thinking_timer.stop()

    def _thinking_step(self) -> None:
        self._thinking_dot_count = self._thinking_dot_count % 6 + 1
        self.full_text = "." * self._thinking_dot_count
        self.typing_prefix = f"【{self.pet_name}】\n"
        self.display_text = self.typing_prefix + self.full_text
        self.update()

    def _typing_step(self) -> None:
        if self.typing_index >= len(self.full_text):
            self.typing_timer.stop()
            return
        self.typing_index += 1
        self.display_text = (
            self.typing_prefix + self.full_text[: self.typing_index]
        )
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.display_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setFont(self.text_font)
        rect = self.rect()
        text_rect = rect.adjusted(
            self.text_x_offset,
            self.text_y_offset,
            -self.text_x_offset,
            -rect.height() // 2 + self.text_y_offset,
        )
        alignment = (
            Qt.AlignLeft | Qt.AlignBottom
            if "\n" in self.display_text
            else Qt.AlignHCenter | Qt.AlignBottom
        )
        painter.setPen(QColor(44, 22, 28))
        for dx, dy in [
            (-self.border_size, 0),
            (self.border_size, 0),
            (0, -self.border_size),
            (0, self.border_size),
            (self.border_size, -self.border_size),
            (self.border_size, self.border_size),
            (-self.border_size, -self.border_size),
            (-self.border_size, self.border_size),
        ]:
            painter.drawText(
                text_rect.translated(dx, dy),
                alignment,
                self.display_text,
            )
        painter.setPen(Qt.white)
        painter.drawText(text_rect, alignment, self.display_text)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if event.y() < 150:
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:
                self._cancel_active_jobs(include_vision=True)
                self.input_mode = True
                self.input_buffer = ""
                self.preedit_text = ""
                self.display_text = (
                    f"【{self.settings.character.user_name}】\n  「...」"
                )
                self.setFocus()
                self.update()
            else:
                self.touch_head = False
                self.head_press_x = None
        elif event.button() == Qt.MiddleButton:
            self.drag_offset = event.pos()
            self.setCursor(Qt.SizeAllCursor)

    def mouseMoveEvent(self, event) -> None:
        if self.touch_head and self.head_press_x is not None:
            if abs(event.x() - self.head_press_x) > 50:
                self.start_thread("主人摸了摸你的头。", role="system")
                self.touch_head = False
        if self.drag_offset is not None and event.buttons() & Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.MiddleButton:
            self.drag_offset = None
            self.setCursor(Qt.ArrowCursor)
            self._adapt_to_current_screen()
            self.remember_window_position()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if (
            hasattr(self, "_screen_resize_timer")
            and self.drag_offset is None
        ):
            self._screen_resize_timer.start()

    def inputMethodQuery(self, query):
        if query in (Qt.ImMicroFocus, Qt.ImCursorRectangle):
            rect = self.rect()
            text_rect = QRect(
                rect.x() + self.text_x_offset,
                rect.y() + self.text_y_offset,
                max(1, rect.width() - 2 * self.text_x_offset),
                max(1, rect.height() // 2 - self.text_y_offset),
            )
            font_metrics = QFontMetrics(self.text_font)
            last_line = (self.display_text or "").split("\n")[-1]
            x = text_rect.x() + min(
                max(0, font_metrics.horizontalAdvance(last_line)),
                max(1, text_rect.width() - 1),
            )
            caret = QRect(
                int(x),
                text_rect.bottom() - font_metrics.height(),
                1,
                font_metrics.height(),
            )
            return caret.intersected(self.rect().adjusted(0, 0, -1, -1))
        return super().inputMethodQuery(query)

    def inputMethodEvent(self, event) -> None:
        if not self.input_mode:
            super().inputMethodEvent(event)
            return
        self.input_buffer += event.commitString()
        self.preedit_text = event.preeditString()
        self._show_input_buffer()

    def keyPressEvent(self, event) -> None:
        if not self.input_mode:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            text = self.input_buffer.strip()
            self.input_mode = False
            self.preedit_text = ""
            if text:
                self.start_thread(text, role="user")
            else:
                self.show_text("主人，你说什么？")
            return
        if event.key() == Qt.Key_Escape:
            self.input_mode = False
            self.show_text("……？", typing=False)
            return
        if event.key() == Qt.Key_Backspace and not self.preedit_text:
            self.input_buffer = self.input_buffer[:-1]
            self._show_input_buffer()
            return
        text = event.text()
        if text and not self.preedit_text:
            self.input_buffer += text
            self._show_input_buffer()

    def _show_input_buffer(self) -> None:
        content = wrap_text(self.input_buffer + self.preedit_text) or "..."
        self.display_text = (
            f"【{self.settings.character.user_name}】\n  「{content}」"
        )
        self.update()

    def clear_history(self) -> None:
        self._cancel_active_jobs()
        self.history.clear()
        self.history_store.clear()
        self.screen_memory_store.clear()
        portrait = self.settings.character.portrait
        outfit = self.settings.character.outfit
        self.update_portrait(
            default_layers(portrait, outfit),
            portrait,
            outfit,
        )
        self.show_text("已经忘掉之前的对话和屏幕事件了。", typing=False)

    def shutdown(self) -> None:
        self._topmost_timer.stop()
        self._screen_resize_timer.stop()
        self.screenshot_timer.stop()
        self.idle_timer.stop()
        self._cancel_active_jobs(include_vision=True)
        self.history_store.save(self.history)
        for worker in list(self._workers.values()):
            worker.wait(250)
        if self._vision_worker is not None:
            self._vision_worker.wait(250)
