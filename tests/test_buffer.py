import unittest

from adaptive_vr.buffer import FeatureBuffer
from adaptive_vr.protocol import DeviceRole, FeaturePacket


def make(role, timestamp, sequence, received=None):
    return FeaturePacket(1, role, f"{role}-01", timestamp, sequence, {}, {}, received)


class BufferTests(unittest.TestCase):
    def test_synchronizes_close_packets(self):
        buffer = FeatureBuffer(sync_tolerance_ms=120)
        self.assertIsNone(buffer.add(make(DeviceRole.UPPER_FACE, 1000, 1)))
        pair = buffer.add(make(DeviceRole.LOWER_FACE, 1080, 1))
        self.assertIsNotNone(pair)
        self.assertEqual(pair.upper.timestamp_ms, 1000)
        self.assertEqual(pair.lower.timestamp_ms, 1080)

    def test_does_not_pair_distant_packets(self):
        buffer = FeatureBuffer(sync_tolerance_ms=120)
        buffer.add(make(DeviceRole.UPPER_FACE, 1000, 1))
        self.assertIsNone(buffer.add(make(DeviceRole.LOWER_FACE, 1300, 1)))

    def test_uses_host_arrival_time_for_independent_device_clocks(self):
        buffer = FeatureBuffer(sync_tolerance_ms=120)
        buffer.add(make(DeviceRole.UPPER_FACE, 50_000, 1, received=10_000))
        pair = buffer.add(make(DeviceRole.LOWER_FACE, 2_000, 1, received=10_040))
        self.assertIsNotNone(pair)
        self.assertEqual(pair.timestamp_ms, 10_040)

    def test_accepts_sequence_reset_after_device_reboot(self):
        buffer = FeatureBuffer(sync_tolerance_ms=120)
        buffer.add(make(DeviceRole.LOWER_FACE, 1_000, 500, received=10_000))
        buffer.add(make(DeviceRole.UPPER_FACE, 2_000, 20, received=20_000))
        pair = buffer.add(make(DeviceRole.LOWER_FACE, 10, 0, received=20_020))
        self.assertIsNotNone(pair)
        self.assertEqual(pair.lower.sequence, 0)


if __name__ == "__main__":
    unittest.main()
