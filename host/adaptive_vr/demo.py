from __future__ import annotations

import argparse
import json
import time

from .adaptation import action_for
from .features import (
    HeadFeatures,
    LearningFeatures,
    LowerFaceFeatures,
    MultimodalSnapshot,
    SpeechFeatures,
    UpperFaceFeatures,
)
from .rules import RuleBasedClassifier
from .stability import StateStabilizer


def scenario_snapshot(name: str, timestamp_ms: int) -> MultimodalSnapshot:
    if name == "confused":
        return MultimodalSnapshot(
            timestamp_ms,
            upper=UpperFaceFeatures(
                gaze_stability=0.75,
                eyebrow_contraction=0.72,
                region_valid=True,
                confidence=0.8,
            ),
            lower=LowerFaceFeatures(lip_compression=0.35, region_valid=True, confidence=0.8),
            speech=SpeechFeatures(repeat_request=True, confusion_keyword=True),
            head=HeadFeatures(stability=0.8, headset_worn=True),
            learning=LearningFeatures(question_active=True, response_time_seconds=9, repeated_mistakes=2, replay_count=1),
        )
    if name == "drowsy":
        return MultimodalSnapshot(
            timestamp_ms,
            upper=UpperFaceFeatures(prolonged_eye_closure_seconds=2.2, region_valid=True, confidence=0.9),
            lower=LowerFaceFeatures(yawn=True, yawn_duration_seconds=2.0, region_valid=True, confidence=0.9),
            head=HeadFeatures(stability=0.25, headset_worn=True),
            learning=LearningFeatures(inactivity_seconds=7),
        )
    return MultimodalSnapshot(
        timestamp_ms,
        upper=UpperFaceFeatures(gaze_stability=0.82, region_valid=True, confidence=0.9),
        lower=LowerFaceFeatures(region_valid=True, confidence=0.9),
        head=HeadFeatures(stability=0.8, headset_worn=True),
        learning=LearningFeatures(recent_accuracy=0.8, interaction_rate_per_minute=4),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the hardware-free engagement inference demo")
    parser.add_argument("--scenario", choices=["focused", "confused", "drowsy"], default="confused")
    args = parser.parse_args()
    classifier = RuleBasedClassifier()
    stabilizer = StateStabilizer(window_size=5, minimum_votes=3)
    stable = None
    prediction = None
    for index in range(5):
        snapshot = scenario_snapshot(args.scenario, int(time.time() * 1000) + index * 100)
        prediction = classifier.predict(snapshot)
        stable = stabilizer.update(prediction)
    action = action_for(stable.state)
    print(
        json.dumps(
            {
                "prediction": prediction.to_dict(),
                "stable_state": stable.state.value,
                "stable_confidence": round(stable.confidence, 4),
                "adaptive_action": asdict_action(action),
            },
            indent=2,
        )
    )


def asdict_action(action):
    return {
        "action": action.action,
        "message": action.message,
        "cooldown_seconds": action.cooldown_seconds,
    }


if __name__ == "__main__":
    main()
