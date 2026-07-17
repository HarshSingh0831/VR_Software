from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .taxonomy import Engagement, STATE_ENGAGEMENT, StudentState


@dataclass(frozen=True, slots=True)
class StatePrediction:
    timestamp_ms: int
    state: StudentState
    confidence: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
    scores: dict[StudentState, float] = field(default_factory=dict)

    @property
    def engagement(self) -> Engagement:
        return STATE_ENGAGEMENT[self.state]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["engagement"] = self.engagement.value
        data["scores"] = {state.value: round(score, 4) for state, score in self.scores.items()}
        data["confidence"] = round(self.confidence, 4)
        return data

