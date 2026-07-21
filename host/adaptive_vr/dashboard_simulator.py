from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
import math
import time

from PIL import Image, ImageDraw

from .taxonomy import StudentState


SIMULATION_STATES = (
    StudentState.FOCUSED,
    StudentState.THINKING,
    StudentState.CONFUSED,
    StudentState.FRUSTRATED,
    StudentState.BORED,
    StudentState.DROWSY,
)


@dataclass(frozen=True, slots=True)
class Preview:
    png: bytes
    age_seconds: float


@dataclass(frozen=True, slots=True)
class SimulatedPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(slots=True)
class SimulatedPiGateway:
    """Hardware-free replacement for PiGateway used by the live dashboard."""

    scenario: str = "auto"
    _active: bool = False
    _participant: str = "P001"
    _session_id: str | None = None
    _label: str = StudentState.FOCUSED.value
    _started_at_ms: int | None = None
    _frames: int = 0
    _tick: int = 0
    _label_counts: Counter[str] = field(default_factory=Counter)

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def current_state(self) -> StudentState:
        if self.scenario != "auto":
            try:
                return StudentState(self.scenario)
            except ValueError:
                pass
        return SIMULATION_STATES[(self._tick // 3) % len(SIMULATION_STATES)]

    def control(self, action: str, **values: str) -> dict[str, object]:
        if action == "start":
            self._active = True
            self._participant = values["participant"]
            self._session_id = values.get("session") or f"sim_{int(time.time())}"
            self._label = values["label"]
            self._started_at_ms = int(time.time() * 1000)
            self._frames = 0
            self._label_counts.clear()
        elif action == "label":
            if not self._active:
                raise ValueError("Start a simulated recording before changing its label.")
            self._label = values["label"]
        elif action == "stop":
            self._active = False
        else:
            raise ValueError(f"Unknown action: {action}")
        return self._control()

    def snapshot(self) -> dict[str, object]:
        self._tick += 1
        if self._active:
            self._frames += 20
            self._label_counts[self._label] += 20
        return {
            "receiver_active": True,
            "lower_active": True,
            "connections": 2,
            "upper_connected": True,
            "lower_connected": True,
            "sync_10s": 20,
            "frames": self._frames,
            "control": self._control(),
            "simulated_state": self.current_state.value,
            "checked_at": time.time(),
        }

    def preview(self, role: str, session_id: str | None = None) -> Preview:
        del session_id
        image = Image.new("L", (640, 360), color=25)
        draw = ImageDraw.Draw(image)
        phase = self._tick / 2.5
        if role == "upper_face":
            self._draw_upper_preview(draw, phase)
        else:
            self._draw_lower_preview(draw, phase)
        output = BytesIO()
        image.save(output, format="PNG")
        return Preview(output.getvalue(), 0.15)

    def label_counts(self, session_id: str) -> Counter[str]:
        del session_id
        return Counter(self._label_counts)

    def _control(self) -> dict[str, object]:
        return {
            "active": self._active,
            "participant_id": self._participant,
            "session_id": self._session_id or "none",
            "label": self._label,
            "started_at_ms": self._started_at_ms or int(time.time() * 1000),
        }

    def _draw_upper_preview(self, draw: ImageDraw.ImageDraw, phase: float) -> None:
        draw.rounded_rectangle((90, 55, 550, 305), radius=80, outline=190, width=4)
        eye_shift = int(math.sin(phase) * 18)
        for center_x in (230, 410):
            draw.ellipse((center_x - 55, 145, center_x + 55, 205), outline=220, width=5)
            draw.ellipse(
                (center_x - 13 + eye_shift, 163, center_x + 13 + eye_shift, 189),
                fill=220,
            )
        draw.arc((180, 100, 280, 155), 200, 340, fill=180, width=5)
        draw.arc((360, 100, 460, 155), 200, 340, fill=180, width=5)

    def _draw_lower_preview(self, draw: ImageDraw.ImageDraw, phase: float) -> None:
        draw.rounded_rectangle((90, 45, 550, 315), radius=90, outline=190, width=4)
        opening = 28 + int((math.sin(phase * 1.3) + 1) * 18)
        draw.ellipse((210, 165 - opening, 430, 165 + opening), outline=225, width=6)
        draw.arc((175, 95, 465, 250), 20, 160, fill=150, width=4)


def simulated_predictions(state: StudentState) -> dict[str, SimulatedPrediction]:
    """Return deterministic demo probabilities for the dashboard scenario."""
    labels = ("angry", "disgust", "fear", "happy", "sad", "surprise", "neutral")
    profiles = {
        StudentState.FOCUSED: (0.03, 0.02, 0.03, 0.15, 0.04, 0.03, 0.70),
        StudentState.THINKING: (0.05, 0.02, 0.08, 0.08, 0.12, 0.04, 0.61),
        StudentState.CONFUSED: (0.08, 0.03, 0.12, 0.03, 0.27, 0.04, 0.43),
        StudentState.FRUSTRATED: (0.50, 0.03, 0.05, 0.02, 0.22, 0.03, 0.15),
        StudentState.BORED: (0.06, 0.03, 0.04, 0.04, 0.20, 0.03, 0.60),
        StudentState.DROWSY: (0.04, 0.02, 0.04, 0.02, 0.38, 0.02, 0.48),
    }
    fused_values = profiles.get(state, profiles[StudentState.FOCUSED])

    def make(values: tuple[float, ...]) -> SimulatedPrediction:
        probabilities = dict(zip(labels, values, strict=True))
        label = max(probabilities, key=probabilities.get)
        return SimulatedPrediction(label, probabilities[label], probabilities)

    upper = make(fused_values)
    lower_raw = tuple(
        value * 0.92 if label != "neutral" else value + 0.08
        for label, value in zip(labels, fused_values, strict=True)
    )
    lower_total = sum(lower_raw)
    lower = make(tuple(value / lower_total for value in lower_raw))
    fused = make(tuple((a + b) / 2 for a, b in zip(upper.probabilities.values(), lower.probabilities.values(), strict=True)))
    return {"upper_face": upper, "lower_face": lower, "fused": fused}
