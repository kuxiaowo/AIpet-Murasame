from __future__ import annotations

import json
from pathlib import Path

from tool.config import get_user_data_dir


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
