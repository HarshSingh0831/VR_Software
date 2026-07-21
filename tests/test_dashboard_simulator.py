from __future__ import annotations

from adaptive_vr.dashboard_simulator import SimulatedPiGateway, simulated_predictions
from adaptive_vr.taxonomy import StudentState


def test_simulated_gateway_reports_live_devices_and_previews() -> None:
    gateway = SimulatedPiGateway()

    status = gateway.snapshot()

    assert status["receiver_active"] is True
    assert status["upper_connected"] is True
    assert status["lower_connected"] is True
    assert status["simulated_state"] == StudentState.FOCUSED.value
    assert gateway.preview("upper_face").png.startswith(b"\x89PNG")
    assert gateway.preview("lower_face").png.startswith(b"\x89PNG")


def test_simulated_recording_tracks_frames_and_labels() -> None:
    gateway = SimulatedPiGateway()
    gateway.control("start", participant="P001", session="demo", label="focused")

    first = gateway.snapshot()
    gateway.control("label", label="confused")
    second = gateway.snapshot()
    gateway.control("stop")

    assert first["frames"] == 20
    assert second["frames"] == 40
    assert gateway.label_counts("demo") == {"focused": 20, "confused": 20}
    assert second["control"]["session_id"] == "demo"


def test_simulated_predictions_are_valid_probabilities() -> None:
    predictions = simulated_predictions(StudentState.CONFUSED)

    assert set(predictions) == {"upper_face", "lower_face", "fused"}
    for prediction in predictions.values():
        assert abs(sum(prediction.probabilities.values()) - 1.0) < 1e-9
        assert prediction.label in prediction.probabilities
        assert prediction.confidence == prediction.probabilities[prediction.label]
