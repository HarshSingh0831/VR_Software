from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from .public_dataset import PublicDatasetRecord, write_manifest
from .taxonomy import StudentState


VALID_STATES = {state.value for state in StudentState}


def subject_split(subject_id: str) -> str:
    bucket = int.from_bytes(hashlib.sha256(subject_id.encode()).digest()[:2], "big") % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def prepare_headset_sessions(
    session_roots: list[str | Path], output_root: str | Path
) -> list[PublicDatasetRecord]:
    output_root = Path(output_root)
    records: list[PublicDatasetRecord] = []
    for raw_root in session_roots:
        session_root = Path(raw_root)
        manifest = session_root / "frames.jsonl"
        if not manifest.exists():
            raise FileNotFoundError(f"Missing {manifest}")
        for line in manifest.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            label = str(row["label"])
            if label not in VALID_STATES:
                continue
            source = session_root / str(row["path"])
            if not source.exists():
                continue
            subject_id = str(row["subject_id"])
            session_id = str(row["session_id"])
            region = str(row["region"])
            split = subject_split(subject_id)
            relative = Path("images") / split / region / label / f"{session_id}_{source.name}"
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            records.append(
                PublicDatasetRecord(
                    path=relative.as_posix(),
                    subject_id=subject_id,
                    label=label,
                    region=region,
                    session_id=session_id,
                    source="AdaptiveVRHeadset",
                    task="vr_state",
                    split=split,
                    original_label=label,
                )
            )
    write_manifest(records, output_root / "manifest.csv")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a fine-tuning dataset from headset sessions")
    parser.add_argument("--session", action="append", required=True)
    parser.add_argument("--output", default="models/datasets/headset_vr")
    args = parser.parse_args()
    records = prepare_headset_sessions(args.session, args.output)
    print(f"Prepared {len(records)} headset images in {args.output}")


if __name__ == "__main__":
    main()
