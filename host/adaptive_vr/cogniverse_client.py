"""Small HTTP bridge from the VR dashboard to the Cogniverse backend.

The hardware pipeline can use the same packet shape directly from the Pi.  This
client is intentionally dependency-free so the Streamlit calibration dashboard
can forward simulator or preview predictions before the Pi is available.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CogniverseConnectionError(RuntimeError):
    """Raised when the Cogniverse endpoint cannot accept a feature packet."""


@dataclass(frozen=True, slots=True)
class CogniverseClient:
    """POST feature packets to a Cogniverse base URL."""

    base_url: str
    timeout_seconds: float = 1.5

    @property
    def endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/device/features"

    def send_features(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(dict(packet), separators=(",", ":")).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise CogniverseConnectionError(
                f"Cogniverse rejected the packet ({error.code}): {detail}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise CogniverseConnectionError(
                f"Cogniverse is unreachable at {self.base_url}: {error}"
            ) from error


def _prediction_payload(prediction: Any, quality: float) -> dict[str, Any]:
    """Convert a CnnPrediction or simulator prediction into API-safe JSON."""

    probabilities = getattr(prediction, "probabilities", {})
    return {
        "expression": str(getattr(prediction, "label", "unknown")),
        "confidence": float(getattr(prediction, "confidence", 0.0)),
        "probabilities": {str(key): float(value) for key, value in probabilities.items()},
        "quality": max(0.0, min(1.0, float(quality))),
    }


def build_dashboard_packet(
    *,
    predictions: Mapping[str, Any],
    upper_quality: float,
    lower_quality: float,
    inference_state: str,
    inference_confidence: float,
    inference_duration_ms: int,
    device_id: str = "streamlit-bridge",
    session_id: str | None = None,
    packet_id: str | None = None,
    receiver_active: bool = False,
) -> dict[str, Any]:
    """Build the same schema expected by ``can/backend/server.mjs``."""

    now_ms = int(time.time() * 1000)
    packet: dict[str, Any] = {
        "schema_version": 1,
        "device_id": device_id,
        "packet_id": packet_id or f"streamlit-{now_ms}",
        "timestamp_ms": now_ms,
        "health": {"packet_loss_pct": 0.0, "receiver_active": receiver_active},
        "upper_face": _prediction_payload(predictions["upper_face"], upper_quality),
        "lower_face": _prediction_payload(predictions["lower_face"], lower_quality),
        "speech": {"quality": 0.0},
        "imu": {"quality": 0.0},
        "inference": {
            "state": str(inference_state),
            "confidence": max(0.0, min(1.0, float(inference_confidence))),
            "duration_ms": max(0, int(inference_duration_ms)),
        },
    }
    if session_id:
        packet["session_id"] = session_id
    return packet
