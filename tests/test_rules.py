import unittest

from adaptive_vr.demo import scenario_snapshot
from adaptive_vr.rules import RuleBasedClassifier
from adaptive_vr.taxonomy import Engagement, StudentState


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RuleBasedClassifier()

    def test_confused_scenario(self):
        prediction = self.classifier.predict(scenario_snapshot("confused", 1000))
        self.assertEqual(prediction.state, StudentState.CONFUSED)
        self.assertEqual(prediction.engagement, Engagement.ENGAGED)
        self.assertGreaterEqual(prediction.confidence, 0.7)

    def test_drowsy_scenario(self):
        prediction = self.classifier.predict(scenario_snapshot("drowsy", 1000))
        self.assertEqual(prediction.state, StudentState.DROWSY)
        self.assertEqual(prediction.engagement, Engagement.NOT_ENGAGED)

    def test_focused_scenario(self):
        prediction = self.classifier.predict(scenario_snapshot("focused", 1000))
        self.assertEqual(prediction.state, StudentState.FOCUSED)


if __name__ == "__main__":
    unittest.main()
