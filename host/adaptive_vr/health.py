from __future__ import annotations

from dataclasses import dataclass
import time

from .protocol import DeviceRole, FeaturePacket


@dataclass(slots=True)
class DeviceHealth:
    last_seen_ms: int = 0
    last_sequence: int = -1
    packets: int = 0
    estimated_dropped_packets: int = 0
    last_confidence: float = 0.0
    region_valid: bool = False

    @property
    def online(self) -> bool:
        return self.last_seen_ms > 0 and (time.time_ns() // 1_000_000 - self.last_seen_ms) < 3_000


class HealthMonitor:
    def __init__(self) -> None:
        self.devices = {role: DeviceHealth() for role in DeviceRole}

    def observe(self, packet: FeaturePacket) -> DeviceHealth:
        health = self.devices[packet.device]
        if health.last_sequence >= 0 and packet.sequence > health.last_sequence + 1:
            health.estimated_dropped_packets += packet.sequence - health.last_sequence - 1
        health.last_seen_ms = packet.received_at_ms or time.time_ns() // 1_000_000
        health.last_sequence = packet.sequence
        health.packets += 1
        health.last_confidence = float(packet.quality.get("confidence", 0.0))
        health.region_valid = bool(packet.quality.get("region_valid", False))
        return health

