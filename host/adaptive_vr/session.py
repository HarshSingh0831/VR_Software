from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .features import MultimodalSnapshot
from .prediction import StatePrediction
from .stability import StableState


class SessionLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        snapshot: MultimodalSnapshot,
        prediction: StatePrediction,
        stable: StableState,
        ground_truth: str | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "snapshot": snapshot.to_dict(),
            "prediction": prediction.to_dict(),
            "stable": {
                **asdict(stable),
                "state": stable.state.value,
            },
            "ground_truth": ground_truth,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")

