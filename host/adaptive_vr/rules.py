from __future__ import annotations

from collections import defaultdict

from .features import MultimodalSnapshot
from .prediction import StatePrediction
from .taxonomy import StudentState


def _present(value: float | None) -> bool:
    return value is not None


class RuleBasedClassifier:
    """Explainable baseline. Thresholds must later be calibrated on headset data."""

    def predict(self, snapshot: MultimodalSnapshot) -> StatePrediction:
        scores: defaultdict[StudentState, float] = defaultdict(float)
        reasons: defaultdict[StudentState, list[str]] = defaultdict(list)

        def add(state: StudentState, score: float, reason: str) -> None:
            scores[state] += score
            reasons[state].append(reason)

        upper, lower = snapshot.upper, snapshot.lower
        speech, head, learning, emotions = (
            snapshot.speech,
            snapshot.head,
            snapshot.learning,
            snapshot.emotions,
        )

        cameras_invalid = not upper.region_valid and not lower.region_valid
        if head.headset_worn is False or (cameras_invalid and learning.inactivity_seconds >= 5):
            add(StudentState.HEADSET_REMOVED, 1.0, "face regions unavailable and headset appears removed")

        if upper.prolonged_eye_closure_seconds >= 1.5:
            add(StudentState.DROWSY, 0.55, "prolonged eye closure")
        if lower.yawn or lower.yawn_duration_seconds >= 1.5:
            add(StudentState.DROWSY, 0.45, "yawn detected")
        if _present(head.stability) and head.stability < 0.35:
            add(StudentState.DROWSY, 0.15, "low head stability")

        away_seconds = max(upper.looking_away_seconds, head.looking_away_seconds)
        if away_seconds >= 2:
            add(StudentState.LOOKING_AWAY, min(0.9, 0.35 + away_seconds / 10), "sustained gaze/head diversion")
        if away_seconds >= 1 and learning.interaction_rate_per_minute is not None:
            if learning.interaction_rate_per_minute < 1:
                add(StudentState.DISTRACTED, 0.35, "attention shifts with low interaction")

        if learning.inactivity_seconds >= 8 and not speech.voice_active:
            add(StudentState.IDLE, min(0.9, 0.4 + learning.inactivity_seconds / 30), "no response or interaction")

        if learning.question_active and speech.voice_active and lower.speaking_motion is not False:
            add(StudentState.ANSWERING, 0.8, "voice and mouth activity while a question is active")

        confusion_evidence = 0.0
        if upper.eyebrow_contraction is not None and upper.eyebrow_contraction >= 0.55:
            confusion_evidence += 0.25
            reasons[StudentState.CONFUSED].append("eyebrow contraction")
        if learning.repeated_mistakes >= 2:
            confusion_evidence += 0.3
            reasons[StudentState.CONFUSED].append("repeated mistakes")
        if speech.confusion_keyword or speech.repeat_request:
            confusion_evidence += 0.35
            reasons[StudentState.CONFUSED].append("confusion or repeat request in speech")
        if learning.replay_count >= 1:
            confusion_evidence += 0.15
            reasons[StudentState.CONFUSED].append("lesson replay")
        if emotions.confusion is not None:
            confusion_evidence += 0.25 * emotions.confusion
        scores[StudentState.CONFUSED] += confusion_evidence

        frustration_evidence = 0.0
        if lower.lip_compression is not None and lower.lip_compression >= 0.55:
            frustration_evidence += 0.25
            reasons[StudentState.FRUSTRATED].append("lip compression")
        if learning.repeated_mistakes >= 3:
            frustration_evidence += 0.3
            reasons[StudentState.FRUSTRATED].append("persistent repeated errors")
        if upper.eyebrow_contraction is not None and upper.eyebrow_contraction >= 0.7:
            frustration_evidence += 0.2
            reasons[StudentState.FRUSTRATED].append("strong eyebrow contraction")
        if emotions.frustration is not None:
            frustration_evidence += 0.3 * emotions.frustration
        if emotions.anger is not None:
            frustration_evidence += 0.15 * emotions.anger
        scores[StudentState.FRUSTRATED] += frustration_evidence

        if learning.question_active and learning.response_time_seconds is not None:
            if 3 <= learning.response_time_seconds <= 15 and confusion_evidence < 0.45:
                add(StudentState.THINKING, 0.55, "deliberate response time without strong confusion evidence")
                if upper.gaze_stability is not None and upper.gaze_stability >= 0.6:
                    add(StudentState.THINKING, 0.15, "stable gaze during question")

        happiness = 0.0
        if lower.lip_corner_raise is not None and lower.lip_corner_raise >= 0.55:
            happiness += 0.45
            reasons[StudentState.HAPPY].append("raised lip corners")
        if emotions.happy is not None:
            happiness += 0.5 * emotions.happy
        if learning.recent_accuracy is not None and learning.recent_accuracy >= 0.8:
            happiness += 0.1
            reasons[StudentState.HAPPY].append("strong recent quiz performance")
        scores[StudentState.HAPPY] += happiness

        boredom = 0.0
        if learning.skip_count >= 2:
            boredom += 0.3
            reasons[StudentState.BORED].append("repeated content skipping")
        if learning.interaction_rate_per_minute is not None and learning.interaction_rate_per_minute < 1:
            boredom += 0.25
            reasons[StudentState.BORED].append("low interaction rate")
        if upper.gaze_stability is not None and upper.gaze_stability < 0.3:
            boredom += 0.15
            reasons[StudentState.BORED].append("unstable gaze")
        if learning.inactivity_seconds >= 4:
            boredom += 0.15
            reasons[StudentState.BORED].append("reduced activity")
        scores[StudentState.BORED] += boredom

        focused = 0.25
        focused_reasons = ["no stronger adverse state detected"]
        if upper.gaze_stability is not None and upper.gaze_stability >= 0.65:
            focused += 0.25
            focused_reasons.append("stable gaze")
        if _present(head.stability) and head.stability >= 0.65:
            focused += 0.15
            focused_reasons.append("stable head position")
        if learning.interaction_rate_per_minute is not None and learning.interaction_rate_per_minute >= 2:
            focused += 0.2
            focused_reasons.append("active lesson interaction")
        if learning.recent_accuracy is not None and learning.recent_accuracy >= 0.65:
            focused += 0.1
            focused_reasons.append("adequate recent performance")
        scores[StudentState.FOCUSED] += focused
        reasons[StudentState.FOCUSED].extend(focused_reasons)

        winner = max(StudentState, key=lambda state: scores[state])
        raw_score = scores[winner]
        confidence = max(0.05, min(0.99, raw_score))
        return StatePrediction(
            timestamp_ms=snapshot.timestamp_ms,
            state=winner,
            confidence=confidence,
            reasons=tuple(reasons[winner]),
            scores=dict(scores),
        )

