from __future__ import annotations

import argparse
import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass

import cv2
import numpy as np
from picamera2 import Picamera2
import websockets


LOGGER = logging.getLogger("adaptive_vr.lower_face")
FRAME_HEADER = struct.Struct("<4sBHHIQ")
CALIBRATION_FRAME_INTERVAL = 1  # 10 FPS at the default 10 Hz capture rate


@dataclass(slots=True)
class LowerFaceMetrics:
    brightness: float
    contrast: float
    sharpness: float
    motion: float
    mouth_open: float | None
    lip_compression: float | None
    speaking_motion: bool
    yawn: bool
    region_valid: bool
    confidence: float


class LowerFaceProcessor:
    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.previous_roi: np.ndarray | None = None
        self.yawn_started_at: float | None = None

    def process(self, rgb: np.ndarray) -> LowerFaceMetrics:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        y1, y2 = int(self.height * 0.12), int(self.height * 0.72)
        x1, x2 = int(self.width * 0.12), int(self.width * 0.88)
        roi = gray[y1:y2, x1:x2]

        brightness = float(np.mean(roi) / 255.0)
        contrast = float(min(1.0, np.std(roi) / 64.0))
        sharpness = float(min(1.0, cv2.Laplacian(roi, cv2.CV_32F).var() / 1000.0))
        region_valid = bool(0.06 < brightness < 0.96 and contrast > 0.03 and sharpness > 0.01)

        small = cv2.resize(roi, (160, 96), interpolation=cv2.INTER_AREA)
        motion = 0.0
        if self.previous_roi is not None:
            motion = float(min(1.0, np.mean(cv2.absdiff(small, self.previous_roi)) / 40.0))
        self.previous_roi = small

        equalized = cv2.equalizeHist(roi)
        _, mask = cv2.threshold(equalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 3))
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_score = 0.0
        mouth_open: float | None = None
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area_ratio = (w * h) / float(roi.shape[0] * roi.shape[1])
            aspect = w / max(1.0, float(h))
            centered = abs((x + w / 2) / roi.shape[1] - 0.5) < 0.35
            if centered and 1.2 <= aspect <= 8.0 and 0.002 <= area_ratio <= 0.20:
                score = area_ratio * min(aspect, 4.0)
                if score > best_score:
                    best_score = score
                    mouth_open = float(min(1.0, (h / roi.shape[0]) / 0.30))

        lip_compression = None if mouth_open is None else float(1.0 - mouth_open)
        speaking_motion = bool(region_valid and motion >= 0.035)

        now = time.monotonic()
        if region_valid and mouth_open is not None and mouth_open >= 0.62:
            self.yawn_started_at = self.yawn_started_at or now
        else:
            self.yawn_started_at = None
        yawn = bool(self.yawn_started_at is not None and now - self.yawn_started_at >= 1.5)

        confidence = 0.0
        if region_valid:
            confidence = min(0.85, 0.30 + 0.25 * contrast + 0.20 * sharpness)
            if mouth_open is None:
                confidence *= 0.55

        return LowerFaceMetrics(
            brightness=brightness,
            contrast=contrast,
            sharpness=sharpness,
            motion=motion,
            mouth_open=mouth_open,
            lip_compression=lip_compression,
            speaking_motion=speaking_motion,
            yawn=yawn,
            region_valid=region_valid,
            confidence=float(confidence),
        )


def packet(metrics: LowerFaceMetrics, sequence: int) -> str:
    return json.dumps(
        {
            "protocol_version": 1,
            "device": "lower_face",
            "device_id": "raspberry-pi-lower-face-01",
            "timestamp_ms": time.monotonic_ns() // 1_000_000,
            "sequence": sequence,
            "features": {
                "mouth_open": metrics.mouth_open,
                "lip_corner_raise": None,
                "lip_compression": metrics.lip_compression,
                "jaw_motion": metrics.motion,
                "speaking_motion": metrics.speaking_motion,
                "yawn": metrics.yawn,
            },
            "quality": {
                "brightness": metrics.brightness,
                "contrast": metrics.contrast,
                "sharpness": metrics.sharpness,
                "region_valid": metrics.region_valid,
                "confidence": metrics.confidence,
            },
        },
        separators=(",", ":"),
    )


def calibration_frame(gray: np.ndarray, sequence: int) -> bytes:
    height, width = gray.shape
    return FRAME_HEADER.pack(
        b"AVF1",
        1,
        width,
        height,
        sequence,
        time.monotonic_ns() // 1_000_000,
    ) + gray.tobytes()


async def stream(uri: str, rate_hz: float, width: int, height: int) -> None:
    camera = Picamera2()
    camera.configure(
        camera.create_video_configuration(main={"size": (width, height), "format": "RGB888"})
    )
    camera.start()
    await asyncio.sleep(1.0)
    processor = LowerFaceProcessor(width, height)
    sequence = 0
    interval = 1.0 / rate_hz
    try:
        while True:
            try:
                async with websockets.connect(
                    uri, ping_interval=10, ping_timeout=10, open_timeout=8
                ) as websocket:
                    LOGGER.info("Connected to %s", uri)
                    while True:
                        started = time.monotonic()
                        frame = camera.capture_array()
                        metrics = processor.process(frame)
                        await websocket.send(packet(metrics, sequence))
                        await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        if sequence % CALIBRATION_FRAME_INTERVAL == 0:
                            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                            gray = cv2.resize(gray, (320, 240), interpolation=cv2.INTER_AREA)
                            await websocket.send(calibration_frame(gray, sequence))
                        sequence += 1
                        await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))
            except (OSError, TimeoutError, websockets.ConnectionClosed) as exc:
                LOGGER.warning("Receiver unavailable: %s; retrying", exc)
                await asyncio.sleep(2.0)
    finally:
        camera.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive VR Raspberry Pi lower-face node")
    parser.add_argument("--receiver", default="ws://127.0.0.1:8765/")
    parser.add_argument("--rate", type=float, default=10.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(stream(args.receiver, args.rate, args.width, args.height))


if __name__ == "__main__":
    main()
