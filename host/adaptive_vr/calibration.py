from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct
import time
from typing import Any

from .protocol import DeviceRole


FRAME_MAGIC = b"AVF1"
FRAME_HEADER = struct.Struct("<4sBHHIQ")
ROLE_TO_CODE = {DeviceRole.UPPER_FACE: 0, DeviceRole.LOWER_FACE: 1}
CODE_TO_ROLE = {value: key for key, value in ROLE_TO_CODE.items()}


@dataclass(frozen=True, slots=True)
class CalibrationFrame:
    role: DeviceRole
    width: int
    height: int
    sequence: int
    timestamp_ms: int
    grayscale: bytes

    def to_bytes(self) -> bytes:
        return FRAME_HEADER.pack(
            FRAME_MAGIC,
            ROLE_TO_CODE[self.role],
            self.width,
            self.height,
            self.sequence,
            self.timestamp_ms,
        ) + self.grayscale

    @classmethod
    def from_bytes(cls, raw: bytes) -> "CalibrationFrame":
        if len(raw) < FRAME_HEADER.size:
            raise ValueError("Calibration frame is shorter than its header")
        magic, role_code, width, height, sequence, timestamp_ms = FRAME_HEADER.unpack_from(raw)
        if magic != FRAME_MAGIC:
            raise ValueError("Unknown binary frame format")
        try:
            role = CODE_TO_ROLE[role_code]
        except KeyError as exc:
            raise ValueError(f"Unknown calibration camera role: {role_code}") from exc
        pixels = raw[FRAME_HEADER.size :]
        if width <= 0 or height <= 0 or len(pixels) != width * height:
            raise ValueError("Calibration frame dimensions do not match its payload")
        return cls(role, width, height, sequence, timestamp_ms, pixels)


class CalibrationRecorder:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.control_path = self.root / "control.json"
        self._control_mtime_ns = -1
        self._control: dict[str, Any] | None = None
        self.frames_recorded = 0

    def _write_preview(self, frame: CalibrationFrame) -> Path:
        """Atomically replace the one-frame live preview for a camera role."""
        preview_path = self.root / "preview" / f"{frame.role.value}.pgm"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = preview_path.with_suffix(".pgm.tmp")
        temporary.write_bytes(
            f"P5\n{frame.width} {frame.height}\n255\n".encode() + frame.grayscale
        )
        temporary.replace(preview_path)
        return preview_path

    def _active_control(self) -> dict[str, Any] | None:
        try:
            stat = self.control_path.stat()
        except FileNotFoundError:
            self._control = None
            self._control_mtime_ns = -1
            return None
        if stat.st_mtime_ns != self._control_mtime_ns:
            self._control = json.loads(self.control_path.read_text(encoding="utf-8"))
            self._control_mtime_ns = stat.st_mtime_ns
        if not self._control or not self._control.get("active"):
            return None
        return self._control

    def record(self, frame: CalibrationFrame, *, received_at_ms: int | None = None) -> Path | None:
        self._write_preview(frame)
        control = self._active_control()
        if control is None:
            return None
        received_at_ms = received_at_ms or time.time_ns() // 1_000_000
        session_id = str(control["session_id"])
        role = frame.role.value
        session_root = self.root / "sessions" / session_id
        relative = Path("images") / role / f"{received_at_ms}_{frame.sequence}.pgm"
        image_path = session_root / relative
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(f"P5\n{frame.width} {frame.height}\n255\n".encode() + frame.grayscale)
        record = {
            "path": relative.as_posix(),
            "subject_id": str(control["participant_id"]),
            "label": str(control["label"]),
            "region": role,
            "session_id": session_id,
            "sequence": frame.sequence,
            "device_timestamp_ms": frame.timestamp_ms,
            "received_at_ms": received_at_ms,
            "width": frame.width,
            "height": frame.height,
        }
        manifest = session_root / "frames.jsonl"
        with manifest.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.frames_recorded += 1
        return image_path
