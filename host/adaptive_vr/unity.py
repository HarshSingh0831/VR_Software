from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from .adaptation import AdaptiveAction
from .prediction import StatePrediction
from .stability import StableState


@dataclass(frozen=True, slots=True)
class UnityEvent:
    event: str
    timestamp_ms: int
    content_id: str | None = None
    value: Any = None

    @classmethod
    def from_json(cls, raw: str | bytes) -> "UnityEvent":
        data = json.loads(raw)
        if not isinstance(data.get("event"), str) or not isinstance(data.get("timestamp_ms"), int):
            raise ValueError("Unity event requires event and timestamp_ms")
        return cls(data["event"], data["timestamp_ms"], data.get("content_id"), data.get("value"))


def adaptive_message(
    prediction: StatePrediction, stable: StableState, action: AdaptiveAction
) -> str:
    return json.dumps(
        {
            "type": "adaptive_state",
            "timestamp_ms": prediction.timestamp_ms,
            "engagement": prediction.engagement.value,
            "predicted_state": prediction.state.value,
            "stable_state": stable.state.value,
            "confidence": round(stable.confidence, 4),
            "state_changed": stable.changed,
            "reasons": list(prediction.reasons),
            "adaptive_action": asdict(action),
        },
        separators=(",", ":"),
    )

