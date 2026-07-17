from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from .taxonomy import StudentState


def safe_component(value: str, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"{name} may contain only letters, numbers, underscore, and hyphen")
    return value


def write_control(root: Path, data: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "control.json.tmp"
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(root / "control.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Control Adaptive VR calibration recording")
    parser.add_argument("--root", default="/var/lib/adaptive-vr/calibration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--participant", required=True)
    start.add_argument("--label", required=True, choices=[state.value for state in StudentState])
    start.add_argument("--session")

    label = subparsers.add_parser("label")
    label.add_argument("value", choices=[state.value for state in StudentState])
    subparsers.add_parser("stop")
    subparsers.add_parser("status")
    args = parser.parse_args()

    root = Path(args.root)
    control_path = root / "control.json"
    current = json.loads(control_path.read_text(encoding="utf-8")) if control_path.exists() else {}

    if args.command == "start":
        participant = safe_component(args.participant, "participant")
        session_id = safe_component(
            args.session or f"{participant}_{time.strftime('%Y%m%d_%H%M%S')}", "session"
        )
        current = {
            "active": True,
            "participant_id": participant,
            "session_id": session_id,
            "label": args.label,
            "started_at_ms": time.time_ns() // 1_000_000,
        }
        write_control(root, current)
    elif args.command == "label":
        if not current.get("active"):
            raise SystemExit("No active calibration session")
        current["label"] = args.value
        current["label_changed_at_ms"] = time.time_ns() // 1_000_000
        write_control(root, current)
    elif args.command == "stop":
        current["active"] = False
        current["stopped_at_ms"] = time.time_ns() // 1_000_000
        write_control(root, current)

    if args.command == "status" and not current:
        print('{"active":false}')
    else:
        print(json.dumps(current, indent=2))


if __name__ == "__main__":
    main()
