from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock

from .protocol import DeviceRole, FeaturePacket


@dataclass(frozen=True, slots=True)
class SynchronizedFeatures:
    timestamp_ms: int
    upper: FeaturePacket
    lower: FeaturePacket


def _sync_time(packet: FeaturePacket) -> int:
    """Use the host arrival clock because independent ESP32 millis() clocks have different epochs."""
    return packet.received_at_ms if packet.received_at_ms is not None else packet.timestamp_ms


class FeatureBuffer:
    def __init__(self, *, sync_tolerance_ms: int = 120, buffer_seconds: int = 30, expected_rate_hz: int = 10):
        self.sync_tolerance_ms = sync_tolerance_ms
        maxlen = max(2, buffer_seconds * expected_rate_hz)
        self._pending = {
            DeviceRole.UPPER_FACE: deque(maxlen=maxlen),
            DeviceRole.LOWER_FACE: deque(maxlen=maxlen),
        }
        self._history: deque[SynchronizedFeatures] = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(self, packet: FeaturePacket) -> SynchronizedFeatures | None:
        with self._lock:
            own = self._pending[packet.device]
            if own and packet.sequence == own[-1].sequence:
                return None
            if own and packet.sequence < own[-1].sequence:
                # A device reboot resets its local sequence counter. Discard
                # the stale unmatched packet so the restarted stream can sync.
                own.clear()
            own.append(packet)

            other_role = (
                DeviceRole.LOWER_FACE if packet.device is DeviceRole.UPPER_FACE else DeviceRole.UPPER_FACE
            )
            other = self._pending[other_role]
            if not other:
                return None

            packet_time = _sync_time(packet)
            match = min(other, key=lambda candidate: abs(_sync_time(candidate) - packet_time))
            if abs(_sync_time(match) - packet_time) > self.sync_tolerance_ms:
                return None

            upper = packet if packet.device is DeviceRole.UPPER_FACE else match
            lower = packet if packet.device is DeviceRole.LOWER_FACE else match
            synchronized = SynchronizedFeatures(
                timestamp_ms=max(_sync_time(upper), _sync_time(lower)), upper=upper, lower=lower
            )
            self._history.append(synchronized)
            own.remove(packet)
            other.remove(match)
            return synchronized

    def history(self) -> tuple[SynchronizedFeatures, ...]:
        with self._lock:
            return tuple(self._history)
