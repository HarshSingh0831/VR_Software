from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import time
from typing import Any


PROTOCOL_VERSION = 1


class DeviceRole(StrEnum):
    UPPER_FACE = "upper_face"
    LOWER_FACE = "lower_face"


UPPER_FEATURES = frozenset(
    {"left_eye_open", "right_eye_open", "blink", "gaze_x", "gaze_y", "eyebrow_raise", "motion"}
)
LOWER_FEATURES = frozenset(
    {"mouth_open", "lip_corner_raise", "lip_compression", "jaw_motion", "speaking_motion", "yawn"}
)


@dataclass(frozen=True, slots=True)
class FeaturePacket:
    protocol_version: int
    device: DeviceRole
    device_id: str
    timestamp_ms: int
    sequence: int
    features: dict[str, float | bool | None]
    quality: dict[str, float | bool]
    received_at_ms: int | None = None

    @classmethod
    def from_json(cls, raw: str | bytes) -> "FeaturePacket":
        try:
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Invalid JSON packet") from exc

        required = {"protocol_version", "device", "device_id", "timestamp_ms", "sequence", "features", "quality"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Missing packet fields: {', '.join(sorted(missing))}")

        if data["protocol_version"] != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {data['protocol_version']}")

        try:
            role = DeviceRole(data["device"])
        except ValueError as exc:
            raise ValueError(f"Unknown device role: {data['device']}") from exc

        if not isinstance(data["features"], dict) or not isinstance(data["quality"], dict):
            raise ValueError("features and quality must be JSON objects")
        if not isinstance(data["timestamp_ms"], int) or data["timestamp_ms"] < 0:
            raise ValueError("timestamp_ms must be a non-negative integer")
        if not isinstance(data["sequence"], int) or data["sequence"] < 0:
            raise ValueError("sequence must be a non-negative integer")

        allowed = UPPER_FEATURES if role is DeviceRole.UPPER_FACE else LOWER_FEATURES
        unknown = set(data["features"]).difference(allowed)
        if unknown:
            raise ValueError(f"Unexpected {role} features: {', '.join(sorted(unknown))}")

        return cls(
            protocol_version=PROTOCOL_VERSION,
            device=role,
            device_id=str(data["device_id"]),
            timestamp_ms=data["timestamp_ms"],
            sequence=data["sequence"],
            features=data["features"],
            quality=data["quality"],
            received_at_ms=time.time_ns() // 1_000_000,
        )
