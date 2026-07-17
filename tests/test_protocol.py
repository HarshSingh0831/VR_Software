import json
import unittest

from adaptive_vr.protocol import DeviceRole, FeaturePacket


def packet(role="upper_face", sequence=1, timestamp=1000):
    features = {"motion": 0.2} if role == "upper_face" else {"jaw_motion": 0.2}
    return json.dumps(
        {
            "protocol_version": 1,
            "device": role,
            "device_id": f"{role}-01",
            "timestamp_ms": timestamp,
            "sequence": sequence,
            "features": features,
            "quality": {"brightness": 0.6, "region_valid": True, "confidence": 0.8},
        }
    )


class ProtocolTests(unittest.TestCase):
    def test_valid_packet(self):
        parsed = FeaturePacket.from_json(packet())
        self.assertIs(parsed.device, DeviceRole.UPPER_FACE)
        self.assertEqual(parsed.sequence, 1)

    def test_rejects_unknown_feature(self):
        data = json.loads(packet())
        data["features"]["mouth_open"] = 0.5
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            FeaturePacket.from_json(json.dumps(data))


if __name__ == "__main__":
    unittest.main()
