from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class LearningEvent:
    event: str
    timestamp_ms: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "timestamp_ms": self.timestamp_ms,
            "payload": self.payload,
        }


def append_learning_event(
    root: str | Path,
    session_id: str,
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    timestamp_ms: int | None = None,
) -> LearningEvent:
    if not session_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in session_id):
        raise ValueError("session_id can contain only letters, numbers, hyphens, and underscores")
    item = LearningEvent(
        event=event,
        timestamp_ms=timestamp_ms if timestamp_ms is not None else time.time_ns() // 1_000_000,
        payload=payload or {},
    )
    folder = Path(root) / session_id
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n")
    return item


def summarize_learning_events(events: Iterable[dict[str, Any]]) -> dict[str, float | int | None]:
    rows = list(events)
    attempts = [row for row in rows if row.get("event") == "quiz_answer"]
    correct = sum(bool(row.get("payload", {}).get("correct")) for row in attempts)
    response_times = [
        float(row["payload"]["response_time_seconds"])
        for row in attempts
        if row.get("payload", {}).get("response_time_seconds") is not None
    ]
    commands = [row for row in rows if row.get("event") == "voice_command"]
    return {
        "events": len(rows),
        "quiz_attempts": len(attempts),
        "correct_answers": correct,
        "accuracy": correct / len(attempts) if attempts else None,
        "average_response_seconds": (
            sum(response_times) / len(response_times) if response_times else None
        ),
        "voice_commands": len(commands),
        "help_requests": sum(
            row.get("payload", {}).get("command") in {"HELP", "SHOW_HINT"}
            for row in commands
        ),
        "replay_requests": sum(
            row.get("payload", {}).get("command")
            in {"REPLAY_SEGMENT", "RESTART_VIDEO", "REPEAT_QUESTION"}
            for row in commands
        ),
    }
