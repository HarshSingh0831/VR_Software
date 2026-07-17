import asyncio
import json
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from adaptive_vr.buffer import FeatureBuffer
from adaptive_vr.receiver import FeatureReceiver


def packet(role, sequence, device_time):
    features = {"motion": 0.1} if role == "upper_face" else {"jaw_motion": 0.1}
    return json.dumps(
        {
            "protocol_version": 1,
            "device": role,
            "device_id": f"integration-{role}",
            "timestamp_ms": device_time,
            "sequence": sequence,
            "features": features,
            "quality": {"brightness": 0.7, "region_valid": True, "confidence": 0.9},
        }
    )


class ReceiverIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_devices_are_accepted_and_synchronized(self):
        feature_buffer = FeatureBuffer(sync_tolerance_ms=250)
        receiver = FeatureReceiver(feature_buffer)
        async with serve(receiver.handle, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            uri = f"ws://127.0.0.1:{port}"

            async def send(role, device_time):
                async with connect(uri) as websocket:
                    await websocket.send(packet(role, 1, device_time))
                    return json.loads(await websocket.recv())

            upper, lower = await asyncio.gather(
                send("upper_face", 50_000),
                send("lower_face", 2_000),
            )

        self.assertTrue(upper["accepted"])
        self.assertTrue(lower["accepted"])
        self.assertEqual(len(feature_buffer.history()), 1)


if __name__ == "__main__":
    unittest.main()
