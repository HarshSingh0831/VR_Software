from __future__ import annotations

import argparse
import asyncio
import logging

from websockets.asyncio.server import ServerConnection, serve

from .buffer import FeatureBuffer
from .calibration import CalibrationFrame, CalibrationRecorder
from .health import HealthMonitor
from .protocol import FeaturePacket


LOGGER = logging.getLogger("adaptive_vr.receiver")


class FeatureReceiver:
    def __init__(self, buffer: FeatureBuffer, calibration: CalibrationRecorder | None = None):
        self.buffer = buffer
        self.health = HealthMonitor()
        self.calibration = calibration

    async def handle(self, websocket: ServerConnection) -> None:
        peer = websocket.remote_address
        LOGGER.info("Device connected: %s", peer)
        try:
            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        frame = CalibrationFrame.from_bytes(message)
                        if self.calibration is not None:
                            saved = self.calibration.record(frame)
                            if saved and self.calibration.frames_recorded % 20 == 0:
                                LOGGER.info(
                                    "Calibration frames recorded: %d",
                                    self.calibration.frames_recorded,
                                )
                        continue
                    packet = FeaturePacket.from_json(message)
                    health = self.health.observe(packet)
                    synchronized = self.buffer.add(packet)
                    await websocket.send(
                        '{"accepted":true,"device":"%s","packets":%d}' % (packet.device, health.packets)
                    )
                    if synchronized:
                        LOGGER.info(
                            "Synchronized upper=%s lower=%s at %d",
                            synchronized.upper.sequence,
                            synchronized.lower.sequence,
                            synchronized.timestamp_ms,
                        )
                except ValueError as exc:
                    LOGGER.warning("Rejected packet from %s: %s", peer, exc)
                    await websocket.send('{"accepted":false,"error":"invalid_packet"}')
        finally:
            LOGGER.info("Device disconnected: %s", peer)


async def run(host: str, port: int, sync_tolerance_ms: int, calibration_root: str | None) -> None:
    calibration = CalibrationRecorder(calibration_root) if calibration_root else None
    receiver = FeatureReceiver(FeatureBuffer(sync_tolerance_ms=sync_tolerance_ms), calibration)
    # The ESP32 WebSocket client streams data but doesn't answer protocol-level
    # keepalive pings. Application packets already provide liveness, so disabling
    # server pings prevents a healthy eye-camera stream being reset every 30 s.
    async with serve(receiver.handle, host, port, ping_interval=None):
        LOGGER.info("Listening on ws://%s:%d", host, port)
        await asyncio.get_running_loop().create_future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Receive local face features from ESP32-S3 modules")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--sync-tolerance-ms", type=int, default=120)
    parser.add_argument("--calibration-root", default="/var/lib/adaptive-vr/calibration")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run(args.host, args.port, args.sync_tolerance_ms, args.calibration_root))


if __name__ == "__main__":
    main()
