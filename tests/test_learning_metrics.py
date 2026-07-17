import unittest

from adaptive_vr.learning_metrics import InteractionEvent, LearningMetricsTracker, QuizAttempt


class LearningMetricsTests(unittest.TestCase):
    def test_builds_recent_learning_features(self):
        tracker = LearningMetricsTracker()
        tracker.record_attempt(QuizAttempt(1000, "q1", False, 8.0))
        tracker.record_attempt(QuizAttempt(2000, "q1", False, 9.0))
        tracker.record_event(InteractionEvent(2500, "replay", "lesson-1"))
        tracker.record_event(InteractionEvent(3000, "help", "lesson-1"))
        result = tracker.snapshot(4000)
        self.assertEqual(result.repeated_mistakes, 2)
        self.assertEqual(result.replay_count, 1)
        self.assertEqual(result.help_count, 1)
        self.assertEqual(result.recent_accuracy, 0.0)


if __name__ == "__main__":
    unittest.main()
