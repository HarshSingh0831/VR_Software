import json

from adaptive_vr.learning_log import append_learning_event, summarize_learning_events


def test_learning_events_are_persisted_and_summarized(tmp_path):
    session = "dc_motor_test"
    append_learning_event(
        tmp_path,
        session,
        "quiz_answer",
        {"correct": True, "response_time_seconds": 3.0},
        timestamp_ms=1000,
    )
    append_learning_event(
        tmp_path,
        session,
        "voice_command",
        {"command": "REPLAY_SEGMENT"},
        timestamp_ms=2000,
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / session / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    summary = summarize_learning_events(rows)
    assert summary["events"] == 2
    assert summary["accuracy"] == 1.0
    assert summary["average_response_seconds"] == 3.0
    assert summary["voice_commands"] == 1
    assert summary["replay_requests"] == 1


def test_learning_event_rejects_unsafe_session_id(tmp_path):
    try:
        append_learning_event(tmp_path, "../outside", "test")
    except ValueError as exc:
        assert "session_id" in str(exc)
    else:
        raise AssertionError("unsafe session ID was accepted")


def test_dc_motor_quiz_has_valid_answer_keys():
    path = __import__("pathlib").Path("config/learning_quiz.json")
    questions = json.loads(path.read_text(encoding="utf-8"))
    assert len(questions) == 14
    assert sum(question["section"].endswith("MID PART 1") for question in questions) == 7
    assert sum(question["section"].endswith("LAST PART") for question in questions) == 7
    assert all(len(question["options"]) == 4 for question in questions)
    assert all(0 <= question["correct_index"] < 4 for question in questions)
    assert [question["correct_index"] for question in questions] == [
        2, 1, 2, 1, 2, 2, 2,
        1, 2, 2, 2, 1, 2, 1,
    ]


def test_cogniverse_content_manifest_preserves_module_order():
    path = __import__("pathlib").Path("config/learning_content.json")
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["repository"] == "Chenikachhabra/cogniverse"
    assert [video["content_id"] for video in content["videos"]] == [
        "main",
        "torque",
        "curved_magnets",
        "current_reverse",
        "multiple_coils",
        "commutator_rings",
        "carbon_brushes",
        "magnets",
        "electromagnet",
    ]
    modules = content["expected_modules"]
    assert {module["content_id"]: module["popup_at_seconds"] for module in modules} == {
        "torque": 422,
        "curved_magnets": 260,
        "current_reverse": 335,
        "multiple_coils": 374,
        "commutator_rings": 290,
        "carbon_brushes": 299,
        "magnets": 73,
        "electromagnet": 155,
    }
    assert all(module["popup_duration_seconds"] == 30 for module in modules)
    assert modules[0]["main_start_seconds"] == 0
    assert modules[-1]["main_end_seconds"] == 2208
    assert all(
        current["main_end_seconds"] == following["main_start_seconds"]
        for current, following in zip(modules, modules[1:])
    )
