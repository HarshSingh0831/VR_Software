import unittest

from adaptive_vr.prediction import StatePrediction
from adaptive_vr.stability import StateStabilizer
from adaptive_vr.taxonomy import StudentState


class StabilityTests(unittest.TestCase):
    def test_state_changes_only_after_sufficient_votes(self):
        stabilizer = StateStabilizer(window_size=5, minimum_votes=3, minimum_confidence=0.5)
        first = stabilizer.update(StatePrediction(1000, StudentState.FOCUSED, 0.8))
        self.assertEqual(first.state, StudentState.FOCUSED)
        stabilizer.update(StatePrediction(1100, StudentState.CONFUSED, 0.8))
        second = stabilizer.update(StatePrediction(1200, StudentState.CONFUSED, 0.8))
        self.assertEqual(second.state, StudentState.FOCUSED)
        changed = stabilizer.update(StatePrediction(1300, StudentState.CONFUSED, 0.8))
        self.assertEqual(changed.state, StudentState.CONFUSED)
        self.assertTrue(changed.changed)


if __name__ == "__main__":
    unittest.main()
