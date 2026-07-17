import unittest

from adaptive_vr.dataset import DatasetRecord, split_by_subject


class DatasetTests(unittest.TestCase):
    def test_subjects_never_cross_splits(self):
        records = [
            DatasetRecord(f"{subject}-{index}.jpg", subject, "focused", "upper", "s1")
            for subject in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
            for index in range(2)
        ]
        splits = split_by_subject(records)
        subject_sets = [{record.subject_id for record in values} for values in splits.values()]
        self.assertTrue(subject_sets[0].isdisjoint(subject_sets[1]))
        self.assertTrue(subject_sets[0].isdisjoint(subject_sets[2]))
        self.assertTrue(subject_sets[1].isdisjoint(subject_sets[2]))
        self.assertEqual(sum(len(values) for values in splits.values()), len(records))


if __name__ == "__main__":
    unittest.main()
