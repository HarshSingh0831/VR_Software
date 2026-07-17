import json

from adaptive_vr.headset_dataset import prepare_headset_sessions, subject_split


def test_subject_split_is_stable():
    assert subject_split("P001") == subject_split("P001")
    assert subject_split("P001") in {"train", "validation", "test"}


def test_prepare_headset_session_copies_valid_labeled_frames(tmp_path):
    session = tmp_path / "session_001"
    image = session / "images" / "upper_face" / "1_1.pgm"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"P5\n2 2\n255\n\x00\x01\x02\x03")
    row = {
        "path": "images/upper_face/1_1.pgm",
        "subject_id": "P001",
        "label": "focused",
        "region": "upper_face",
        "session_id": "session_001",
    }
    (session / "frames.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    output = tmp_path / "prepared"
    records = prepare_headset_sessions([session], output)
    assert len(records) == 1
    assert records[0].task == "vr_state"
    assert (output / records[0].path).exists()
