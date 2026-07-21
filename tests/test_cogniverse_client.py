from __future__ import annotations

from dataclasses import dataclass

from adaptive_vr.cogniverse_client import build_dashboard_packet


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def test_build_dashboard_packet_matches_cogniverse_schema() -> None:
    prediction = Prediction("neutral", 0.8, {"neutral": 0.8, "sad": 0.2})
    packet = build_dashboard_packet(
        predictions={"upper_face": prediction, "lower_face": prediction, "fused": prediction},
        upper_quality=0.9,
        lower_quality=0.8,
        inference_state="confused",
        inference_confidence=0.84,
        inference_duration_ms=4_000,
        session_id="ABC123",
    )

    assert packet["schema_version"] == 1
    assert packet["session_id"] == "ABC123"
    assert packet["upper_face"]["quality"] == 0.9
    assert packet["inference"] == {
        "state": "confused",
        "confidence": 0.84,
        "duration_ms": 4_000,
    }
