import json
import unittest

from adaptive_vr.adaptation import action_for
from adaptive_vr.prediction import StatePrediction
from adaptive_vr.stability import StableState
from adaptive_vr.taxonomy import StudentState
from adaptive_vr.unity import UnityEvent, adaptive_message


class UnityTests(unittest.TestCase):
    def test_parses_event(self):
        event = UnityEvent.from_json(
            '{"event":"replay","timestamp_ms":1000,"content_id":"lesson-1"}'
        )
        self.assertEqual(event.event, "replay")

    def test_builds_adaptive_message(self):
        prediction = StatePrediction(1000, StudentState.CONFUSED, 0.8, ("repeated mistakes",))
        stable = StableState(StudentState.CONFUSED, 0.75, 900, True)
        message = json.loads(
            adaptive_message(prediction, stable, action_for(StudentState.CONFUSED))
        )
        self.assertEqual(message["stable_state"], "confused")
        self.assertEqual(message["adaptive_action"]["action"], "simplify")


if __name__ == "__main__":
    unittest.main()
