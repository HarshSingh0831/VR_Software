import unittest

from adaptive_vr.health import HealthMonitor
from adaptive_vr.protocol import DeviceRole, FeaturePacket


class HealthTests(unittest.TestCase):
    def test_tracks_dropped_sequences_and_quality(self):
        monitor = HealthMonitor()
        first = FeaturePacket(1, DeviceRole.UPPER_FACE, "upper-01", 10, 1, {}, {}, 1000)
        third = FeaturePacket(
            1,
            DeviceRole.UPPER_FACE,
            "upper-01",
            30,
            3,
            {},
            {"confidence": 0.75, "region_valid": True},
            1020,
        )
        monitor.observe(first)
        health = monitor.observe(third)
        self.assertEqual(health.estimated_dropped_packets, 1)
        self.assertEqual(health.packets, 2)
        self.assertTrue(health.region_valid)
        self.assertEqual(health.last_confidence, 0.75)


if __name__ == "__main__":
    unittest.main()
