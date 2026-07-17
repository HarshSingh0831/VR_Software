from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class UpperFaceFeatures:
    left_eye_open: float | None = None
    right_eye_open: float | None = None
    blink_rate_per_minute: float | None = None
    prolonged_eye_closure_seconds: float = 0.0
    gaze_x: float | None = None
    gaze_y: float | None = None
    gaze_stability: float | None = None
    looking_away_seconds: float = 0.0
    eyebrow_raise: float | None = None
    eyebrow_contraction: float | None = None
    motion: float | None = None
    region_valid: bool = False
    confidence: float = 0.0


@dataclass(slots=True)
class LowerFaceFeatures:
    mouth_open: float | None = None
    lip_corner_raise: float | None = None
    lip_compression: float | None = None
    jaw_motion: float | None = None
    speaking_motion: bool | None = None
    yawn: bool = False
    yawn_duration_seconds: float = 0.0
    region_valid: bool = False
    confidence: float = 0.0


@dataclass(slots=True)
class SpeechFeatures:
    voice_active: bool = False
    hesitation_count: int = 0
    pause_duration_seconds: float = 0.0
    repeat_request: bool = False
    help_request: bool = False
    confusion_keyword: bool = False
    detected_command: str | None = None


@dataclass(slots=True)
class HeadFeatures:
    pitch: float | None = None
    yaw: float | None = None
    roll: float | None = None
    stability: float | None = None
    looking_away_seconds: float = 0.0
    headset_worn: bool | None = None


@dataclass(slots=True)
class LearningFeatures:
    question_active: bool = False
    response_time_seconds: float | None = None
    recent_accuracy: float | None = None
    repeated_mistakes: int = 0
    improvement: float | None = None
    replay_count: int = 0
    skip_count: int = 0
    help_count: int = 0
    inactivity_seconds: float = 0.0
    interaction_rate_per_minute: float | None = None


@dataclass(slots=True)
class EmotionProbabilities:
    neutral: float | None = None
    happy: float | None = None
    anger: float | None = None
    confusion: float | None = None
    frustration: float | None = None


@dataclass(slots=True)
class MultimodalSnapshot:
    timestamp_ms: int
    upper: UpperFaceFeatures = field(default_factory=UpperFaceFeatures)
    lower: LowerFaceFeatures = field(default_factory=LowerFaceFeatures)
    speech: SpeechFeatures = field(default_factory=SpeechFeatures)
    head: HeadFeatures = field(default_factory=HeadFeatures)
    learning: LearningFeatures = field(default_factory=LearningFeatures)
    emotions: EmotionProbabilities = field(default_factory=EmotionProbabilities)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

