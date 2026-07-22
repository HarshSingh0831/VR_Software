import unittest

from adaptive_vr.commands import build_command_event, detect_command


class CommandCatalogueTests(unittest.TestCase):
    def test_hinglish_replay_segment(self):
        command = detect_command("ye part dobara chalao")
        self.assertEqual(command.action, "REPLAY_SEGMENT")

    def test_quiz_answer_requires_quiz_context(self):
        self.assertIsNone(detect_command("option b"))
        command = detect_command("option b", context="quiz")
        self.assertEqual(command.action, "ANSWER_B")

    def test_audio_command(self):
        self.assertEqual(detect_command("aawaz tez karo").action, "VOLUME_UP")

    def test_session_command(self):
        self.assertEqual(detect_command("lesson khatam karo").action, "END_SESSION")

    def test_continue_main_video_command(self):
        self.assertEqual(
            detect_command("continue main video").action,
            "RETURN_TO_MAIN_VIDEO",
        )

    def test_documented_event_format(self):
        command = detect_command("ye part dobara chalao")
        event = build_command_event(
            command,
            session_id="session_004",
            recognized_text="ye part dobara chalao",
            detected_language="hinglish",
            timestamp_ms=1784185200000,
            parameters={"segment_id": "motor_torque", "seconds": 10},
        )
        data = event.to_dict()
        self.assertEqual(data["command"], "REPLAY_SEGMENT")
        self.assertEqual(data["source"], "student_voice")
        self.assertTrue(data["command_id"].startswith("cmd_"))


if __name__ == "__main__":
    unittest.main()
