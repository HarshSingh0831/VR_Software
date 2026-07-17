from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from .public_dataset import PublicDatasetRecord, read_public_manifest
from .train_baseline import image_features


def _region_records(
    records: list[PublicDatasetRecord], task: str, region: str, split: str
) -> list[PublicDatasetRecord]:
    return sorted(
        (
            record
            for record in records
            if record.task == task and record.region == region and record.split == split
        ),
        key=lambda record: record.subject_id,
    )


def evaluate_fusion(
    manifest: str | Path,
    model_dir: str | Path,
    *,
    task: str = "expression",
    split: str = "test",
) -> dict[str, object]:
    manifest = Path(manifest)
    model_dir = Path(model_dir)
    records = read_public_manifest(manifest)
    upper_records = _region_records(records, task, "upper_face", split)
    lower_records = _region_records(records, task, "lower_face", split)
    if not upper_records or len(upper_records) != len(lower_records):
        raise ValueError("Upper/lower evaluation records are missing or unpaired")
    for upper, lower in zip(upper_records, lower_records, strict=True):
        if upper.subject_id != lower.subject_id or upper.label != lower.label:
            raise ValueError(f"Unpaired camera records for {upper.subject_id}")

    upper_payload = joblib.load(model_dir / f"{task}_upper_face_baseline.joblib")
    lower_payload = joblib.load(model_dir / f"{task}_lower_face_baseline.joblib")
    classes = list(upper_payload["model"].classes_)
    if classes != list(lower_payload["model"].classes_):
        raise ValueError("Upper and lower models use different class orders")
    upper_x = np.stack([image_features(manifest.parent / row.path) for row in upper_records])
    lower_x = np.stack([image_features(manifest.parent / row.path) for row in lower_records])
    upper_probability = upper_payload["model"].predict_proba(upper_x)
    lower_probability = lower_payload["model"].predict_proba(lower_x)
    fused_probability = (upper_probability + lower_probability) / 2.0
    truth = np.asarray([record.label for record in upper_records])

    def metrics(probability: np.ndarray) -> dict[str, object]:
        predicted = np.asarray(classes)[probability.argmax(axis=1)]
        return {
            "accuracy": float(accuracy_score(truth, predicted)),
            "macro_f1": float(f1_score(truth, predicted, average="macro", zero_division=0)),
            "classification_report": classification_report(
                truth, predicted, labels=classes, output_dict=True, zero_division=0
            ),
            "confusion_matrix": confusion_matrix(truth, predicted, labels=classes).tolist(),
        }

    result: dict[str, object] = {
        "task": task,
        "split": split,
        "samples": len(truth),
        "classes": classes,
        "upper_face": metrics(upper_probability),
        "lower_face": metrics(lower_probability),
        "equal_probability_fusion": metrics(fused_probability),
    }
    (model_dir / f"{task}_{split}_fusion_metrics.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate upper/lower probability fusion")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--model-dir", default="models/trained")
    parser.add_argument("--task", default="expression")
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate_fusion(args.manifest, args.model_dir, task=args.task, split=args.split),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
