from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .prediction import StatePrediction
from .taxonomy import StudentState


@dataclass(frozen=True, slots=True)
class StableState:
    state: StudentState
    confidence: float
    since_ms: int
    changed: bool


class StateStabilizer:
    def __init__(self, *, window_size: int = 8, minimum_votes: int = 5, minimum_confidence: float = 0.45):
        self.window: deque[StatePrediction] = deque(maxlen=window_size)
        self.minimum_votes = minimum_votes
        self.minimum_confidence = minimum_confidence
        self.current: StudentState | None = None
        self.since_ms = 0

    def update(self, prediction: StatePrediction) -> StableState:
        self.window.append(prediction)
        weighted: dict[StudentState, float] = {}
        votes: dict[StudentState, int] = {}
        for item in self.window:
            weighted[item.state] = weighted.get(item.state, 0.0) + item.confidence
            votes[item.state] = votes.get(item.state, 0) + 1

        candidate = max(weighted, key=weighted.get)
        candidate_confidence = weighted[candidate] / votes[candidate]
        accepted = votes[candidate] >= self.minimum_votes and candidate_confidence >= self.minimum_confidence
        changed = False
        if accepted and candidate != self.current:
            self.current = candidate
            self.since_ms = prediction.timestamp_ms
            changed = True
        if self.current is None:
            self.current = prediction.state
            self.since_ms = prediction.timestamp_ms

        current_items = [item.confidence for item in self.window if item.state == self.current]
        confidence = sum(current_items) / len(current_items) if current_items else prediction.confidence
        return StableState(self.current, confidence, self.since_ms, changed)

