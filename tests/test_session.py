import json
from pathlib import Path
import tempfile
import unittest

from adaptive_vr.demo import scenario_snapshot
from adaptive_vr.rules import RuleBasedClassifier
from adaptive_vr.session import SessionLogger
from adaptive_vr.stability import StateStabilizer


class SessionTests(unittest.TestCase):
    def test_writes_jsonl_record(self):
        snapshot = scenario_snapshot("confused", 1000)
        prediction = RuleBasedClassifier().predict(snapshot)
        stable = StateStabilizer(window_size=1, minimum_votes=1).update(prediction)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            SessionLogger(path).append(
                snapshot=snapshot,
                prediction=prediction,
                stable=stable,
                ground_truth="confused",
            )
            record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["prediction"]["state"], "confused")
        self.assertEqual(record["ground_truth"], "confused")


if __name__ == "__main__":
    unittest.main()
