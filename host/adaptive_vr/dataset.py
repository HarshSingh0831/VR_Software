from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import random


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    path: str
    subject_id: str
    label: str
    region: str
    session_id: str


REQUIRED_COLUMNS = {"path", "subject_id", "label", "region", "session_id"}


def read_manifest(path: str | Path) -> list[DatasetRecord]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Manifest missing columns: {', '.join(sorted(missing))}")
        return [DatasetRecord(**{name: row[name] for name in REQUIRED_COLUMNS}) for row in reader]


def split_by_subject(
    records: list[DatasetRecord], *, train: float = 0.7, validation: float = 0.15, seed: int = 42
) -> dict[str, list[DatasetRecord]]:
    if not 0 < train < 1 or not 0 <= validation < 1 or train + validation >= 1:
        raise ValueError("Invalid split fractions")
    subjects = sorted({record.subject_id for record in records})
    random.Random(seed).shuffle(subjects)
    train_end = round(len(subjects) * train)
    validation_end = train_end + round(len(subjects) * validation)
    groups = {
        "train": set(subjects[:train_end]),
        "validation": set(subjects[train_end:validation_end]),
        "test": set(subjects[validation_end:]),
    }
    return {
        split: [record for record in records if record.subject_id in members]
        for split, members in groups.items()
    }

