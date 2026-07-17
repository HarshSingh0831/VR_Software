from __future__ import annotations

import argparse
import asyncio
import json
import math
import time

from websockets.asyncio.client import connect


def feature_packet(role: str, sequence: int, started: float) -> str:
    elapsed = time.monotonic() - started
    pulse = (math.sin(elapsed * 3.0) + 1.0) / 2.0
    if role == "upper_face":
        features = {
            "left_eye_open": 0.25 + 0.65 * pulse,
            "right_eye_open": 0.25 + 0.65 * pulse,
            "blink": pulse < 0.12,
            "gaze_x": math.sin(elapsed) * 0.2,
            "gaze_y": 0.0,
            "eyebrow_raise": 0.3,
            "motion": 0.1,
        }
    else:
        features = {
            "mouth_open": 0.1 + 0.3 * pulse,
            "lip_corner_raise": 0.25,
            "lip_compression": 0.05,
            "jaw_motion": 0.2,
            "speaking_motion": pulse > 0.55,
            "yawn": False,
        }
    return json.dumps(
        {
            "protocol_version": 1,
            "device": role,
            "device_id": f"sim-{role}-01",
            "timestamp_ms": int(elapsed * 1000),
            "sequence": sequence,
            "features": features,
            "quality": {"brightness": 0.7, "region_valid": True, "confidence": 0.9},
        }
    )


async def simulate_device(uri: str, role: str, duration: float, rate_hz: float) -> None:
    started = time.monotonic()
    async with connect(uri) as websocket:
        sequence = 0
        while time.monotonic() - started < duration:
            await websocket.send(feature_packet(role, sequence, started))
            response = json.loads(await websocket.recv())
            if not response.get("accepted"):
                raise RuntimeError(f"Receiver rejected {role} packet")
            sequence += 1
            await asyncio.sleep(1.0 / rate_hz)
    print(f"{role}: sent {sequence} accepted packets")


async def run(uri: str, duration: float, rate_hz: float) -> None:
    await asyncio.gather(
        simulate_device(uri, "upper_face", duration, rate_hz),
        simulate_device(uri, "lower_face", duration, rate_hz),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate both ESP32 face processors")
    parser.add_argument("--uri", default="ws://127.0.0.1:8765")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--rate", type=float, default=10.0)
    args = parser.parse_args()
    asyncio.run(run(args.uri, args.duration, args.rate))


if __name__ == "__main__":
    main()
