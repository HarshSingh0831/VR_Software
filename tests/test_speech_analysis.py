import unittest

from adaptive_vr.commands import detect_command, normalize_transcript
from adaptive_vr.speech_analysis import analyze_transcript


class BilingualSpeechTests(unittest.TestCase):
    def test_hindi_pause_command(self):
        command = detect_command("वीडियो रोक दो")
        self.assertEqual(command.action, "PAUSE")

    def test_hinglish_next_command(self):
        command = detect_command("agla video")
        self.assertEqual(command.action, "NEXT")

    def test_hindi_confusion_phrase(self):
        event = analyze_transcript(
            "मुझे समझ नहीं आया",
            language="hi",
            confidence=0.9,
            timestamp_ms=1000,
            context="confusion",
        )
        self.assertTrue(event.confusion_keyword)

    def test_hindi_help_phrase(self):
        event = analyze_transcript(
            "मुझे मदद चाहिए",
            language="hi",
            confidence=0.9,
            timestamp_ms=1000,
        )
        self.assertTrue(event.help_request)
        self.assertEqual(event.command.action, "HELP")

    def test_normalization_preserves_devanagari_marks(self):
        self.assertEqual(normalize_transcript("हाँ!"), "हाँ")


if __name__ == "__main__":
    unittest.main()
