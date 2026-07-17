import unittest

from adaptive_vr.evaluation import classification_report
from adaptive_vr.taxonomy import StudentState


class EvaluationTests(unittest.TestCase):
    def test_calculates_accuracy_and_class_metrics(self):
        truth = [StudentState.FOCUSED, StudentState.FOCUSED, StudentState.CONFUSED]
        predicted = [StudentState.FOCUSED, StudentState.CONFUSED, StudentState.CONFUSED]
        report = classification_report(truth, predicted)
        self.assertAlmostEqual(report.accuracy, 2 / 3)
        self.assertEqual(report.by_class[StudentState.CONFUSED].support, 1)


if __name__ == "__main__":
    unittest.main()
