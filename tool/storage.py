from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from tool.config import get_user_data_dir


class ScreenMemoryEntry(BaseModel):
    occurred_at: str = Field(max_length=40)
    software: str = Field(default="", max_length=120)
    activity: str = Field(default="", max_length=1_200)
    topic: str = Field(default="", max_length=500)
    change_summary: str = Field(min_length=1, max_length=1_200)

    @classmethod
    def now(cls, **values) -> "ScreenMemoryEntry":
        return cls(
            occurred_at=datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            **values,
        )

    def event_key(self) -> tuple[object, ...]:
        return (
            self.software.casefold(),
            self.activity.casefold(),
            self.topic.casefold(),
            self.change_summary.casefold(),
        )


class ScreenMemoryStore:
    def __init__(self, path: Path | None = None, limit: int = 12):
        self.path = path or (get_user_data_dir() / "screen_memory.json")
        self.limit = max(1, limit)
        self.entries = self.load()

    def load(self) -> list[ScreenMemoryEntry]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        events = payload.get("events", [])
        if not isinstance(events, list):
            return []
        valid: list[ScreenMemoryEntry] = []
        for event in events:
            try:
                valid.append(ScreenMemoryEntry.model_validate(event))
            except ValidationError:
                continue
        return valid[-self.limit :]

    def remember(self, entry: ScreenMemoryEntry) -> bool:
        if (
            self.entries
            and self.entries[-1].event_key() == entry.event_key()
        ):
            return False
        self.entries.append(entry)
        self.entries = self.entries[-self.limit :]
        self.save()
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "events": [
                entry.model_dump(mode="json") for entry in self.entries
            ]
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def prompt_text(
        self,
        *,
        max_entries: int = 8,
        max_characters: int = 2_400,
    ) -> str:
        selected: list[dict] = []
        used = 2
        for entry in reversed(self.entries[-max_entries:]):
            payload = entry.model_dump(mode="json")
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            extra = len(encoded) + (1 if selected else 0)
            if selected and used + extra > max_characters:
                break
            selected.append(payload)
            used += extra
        if not selected:
            return ""
        selected.reverse()
        return json.dumps(
            selected,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def clear(self) -> None:
        self.entries.clear()
        self.save()


class HistoryStore:
    def __init__(self, path: Path | None = None, limit: int = 30):
        self.path = path or (get_user_data_dir() / "history.json")
        self.limit = max(4, limit)

    def load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return []
        valid = [
            message
            for message in messages
            if isinstance(message, dict)
            and message.get("role") in {"user", "assistant"}
            and isinstance(message.get("content"), str)
        ]
        return valid[-self.limit :]

    def save(self, messages: list[dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"messages": messages[-self.limit :]}
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def clear(self) -> None:
        self.save([])
