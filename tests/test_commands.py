import unittest

from adaptive_vr.commands import detect_command


class CommandTests(unittest.TestCase):
    def test_prefers_specific_long_phrase(self):
        result = detect_command("Please pause video now")
        self.assertEqual(result.action, "PAUSE")
        self.assertEqual(result.matched_phrase, "pause video")

    def test_does_not_match_word_fragment(self):
        self.assertIsNone(detect_command("display the lesson"))

    def test_ambiguous_yes_requires_confusion_context(self):
        self.assertIsNone(detect_command("yes"))
        self.assertEqual(detect_command("yes", context="confusion").action, "CONFUSION_YES")


if __name__ == "__main__":
    unittest.main()
