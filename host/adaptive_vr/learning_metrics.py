from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .features import LearningFeatures


@dataclass(frozen=True, slots=True)
class QuizAttempt:
    timestamp_ms: int
    question_id: str
    correct: bool
    response_time_seconds: float


@dataclass(frozen=True, slots=True)
class InteractionEvent:
    timestamp_ms: int
    event: str
    content_id: str | None = None


class LearningMetricsTracker:
    def __init__(self, *, history_size: int = 20):
        self.attempts: deque[QuizAttempt] = deque(maxlen=history_size)
        self.events: deque[InteractionEvent] = deque(maxlen=200)
        self.last_activity_ms: int | None = None
        self.question_started_ms: int | None = None

    def start_question(self, timestamp_ms: int) -> None:
        self.question_started_ms = timestamp_ms
        self.last_activity_ms = timestamp_ms

    def record_attempt(self, attempt: QuizAttempt) -> None:
        self.attempts.append(attempt)
        self.last_activity_ms = attempt.timestamp_ms
        self.question_started_ms = None

    def record_event(self, event: InteractionEvent) -> None:
        self.events.append(event)
        self.last_activity_ms = event.timestamp_ms

    def snapshot(self, now_ms: int) -> LearningFeatures:
        recent = list(self.attempts)[-10:]
        accuracy = sum(item.correct for item in recent) / len(recent) if recent else None
        repeated_mistakes = 0
        if recent:
            latest_question = recent[-1].question_id
            repeated_mistakes = sum(not item.correct for item in recent if item.question_id == latest_question)
        one_minute_ago = now_ms - 60_000
        recent_events = [event for event in self.events if event.timestamp_ms >= one_minute_ago]
        count = lambda name: sum(event.event == name for event in recent_events)
        inactivity = 0.0 if self.last_activity_ms is None else max(0.0, (now_ms - self.last_activity_ms) / 1000)
        response_time = (
            max(0.0, (now_ms - self.question_started_ms) / 1000)
            if self.question_started_ms is not None
            else None
        )
        return LearningFeatures(
            question_active=self.question_started_ms is not None,
            response_time_seconds=response_time,
            recent_accuracy=accuracy,
            repeated_mistakes=repeated_mistakes,
            replay_count=count("replay"),
            skip_count=count("skip"),
            help_count=count("help"),
            inactivity_seconds=inactivity,
            interaction_rate_per_minute=float(len(recent_events)),
        )

