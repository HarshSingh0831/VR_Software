import json

import pytest

from adaptive_vr.calibration import CalibrationFrame, CalibrationRecorder
from adaptive_vr.protocol import DeviceRole


def test_binary_frame_round_trip():
    original = CalibrationFrame(DeviceRole.UPPER_FACE, 4, 2, 7, 1234, bytes(range(8)))
    assert CalibrationFrame.from_bytes(original.to_bytes()) == original


def test_binary_frame_rejects_wrong_payload_size():
    raw = CalibrationFrame(DeviceRole.LOWER_FACE, 4, 2, 7, 1234, bytes(range(8))).to_bytes()
    with pytest.raises(ValueError):
        CalibrationFrame.from_bytes(raw[:-1])


def test_recorder_is_disabled_until_session_starts(tmp_path):
    recorder = CalibrationRecorder(tmp_path)
    frame = CalibrationFrame(DeviceRole.UPPER_FACE, 2, 2, 1, 10, b"\x00\x01\x02\x03")
    assert recorder.record(frame, received_at_ms=20) is None
    preview = tmp_path / "preview" / "upper_face.pgm"
    assert preview.exists()
    assert preview.read_bytes().startswith(b"P5\n2 2\n255\n")

    (tmp_path / "control.json").write_text(
        json.dumps(
            {
                "active": True,
                "participant_id": "P001",
                "session_id": "test_session",
                "label": "focused",
            }
        ),
        encoding="utf-8",
    )
    saved = recorder.record(frame, received_at_ms=20)
    assert saved is not None and saved.exists()
    assert saved.read_bytes().startswith(b"P5\n2 2\n255\n")
    record = json.loads(
        (tmp_path / "sessions" / "test_session" / "frames.jsonl").read_text(encoding="utf-8")
    )
    assert record["subject_id"] == "P001"
    assert record["region"] == "upper_face"


def test_preview_is_overwritten_instead_of_accumulated(tmp_path):
    recorder = CalibrationRecorder(tmp_path)
    first = CalibrationFrame(DeviceRole.LOWER_FACE, 2, 2, 1, 10, b"\x00\x01\x02\x03")
    second = CalibrationFrame(DeviceRole.LOWER_FACE, 2, 2, 2, 20, b"\x04\x05\x06\x07")

    recorder.record(first)
    recorder.record(second)

    previews = list((tmp_path / "preview").glob("*.pgm"))
    assert len(previews) == 1
    assert previews[0].read_bytes().endswith(second.grayscale)
