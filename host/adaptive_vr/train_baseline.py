from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import joblib
import numpy as np
from PIL import Image, ImageOps
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .public_dataset import PublicDatasetRecord, read_public_manifest


def image_features(path: str | Path, *, mirror: bool = False) -> np.ndarray:
    with Image.open(path) as image:
        grayscale = ImageOps.grayscale(image)
        if mirror:
            grayscale = ImageOps.mirror(grayscale)
        resized = grayscale.resize((32, 16), Image.Resampling.BILINEAR)
        pixels = np.asarray(resized, dtype=np.float32) / 255.0
    gradient_x = np.diff(pixels, axis=1, prepend=pixels[:, :1])
    gradient_y = np.diff(pixels, axis=0, prepend=pixels[:1, :])
    magnitude = np.sqrt(gradient_x * gradient_x + gradient_y * gradient_y)
    hist, _ = np.histogram(pixels, bins=16, range=(0.0, 1.0), density=True)
    return np.concatenate((pixels.ravel(), magnitude.ravel(), hist.astype(np.float32)))


def _records_for(
    records: list[PublicDatasetRecord], task: str, region: str, split: str
) -> list[PublicDatasetRecord]:
    return [
        record
        for record in records
        if record.task == task and record.region == region and record.split == split
    ]


def _matrix(records: list[PublicDatasetRecord], root: Path, augment: bool) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    labels: list[str] = []
    for record in records:
        path = root / record.path
        features.append(image_features(path))
        labels.append(record.label)
        if augment:
            features.append(image_features(path, mirror=True))
            labels.append(record.label)
    if not features:
        raise ValueError("No matching images found in the requested manifest split")
    return np.stack(features), np.asarray(labels)


def train(
    manifest: str | Path,
    output: str | Path,
    *,
    task: str,
    region: str,
) -> dict[str, object]:
    manifest = Path(manifest)
    records = read_public_manifest(manifest)
    train_records = _records_for(records, task, region, "train")
    validation_records = _records_for(records, task, region, "validation")
    if not validation_records:
        validation_records = _records_for(records, task, region, "test")
    root = manifest.parent
    train_x, train_y = _matrix(train_records, root, augment=True)
    validation_x, validation_y = _matrix(validation_records, root, augment=False)

    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                SGDClassifier(
                    loss="log_loss",
                    class_weight="balanced",
                    early_stopping=True,
                    validation_fraction=0.1,
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )
    started = time.time()
    model.fit(train_x, train_y)
    predicted = model.predict(validation_x)
    labels = sorted(set(train_y) | set(validation_y))
    report: dict[str, object] = {
        "task": task,
        "region": region,
        "train_images_with_augmentation": int(len(train_y)),
        "validation_images": int(len(validation_y)),
        "classes": labels,
        "accuracy": float(accuracy_score(validation_y, predicted)),
        "macro_f1": float(f1_score(validation_y, predicted, average="macro", zero_division=0)),
        "classification_report": classification_report(
            validation_y, predicted, labels=labels, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(validation_y, predicted, labels=labels).tolist(),
        "training_seconds": round(time.time() - started, 3),
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "task": task,
            "region": region,
            "classes": labels,
            "feature_version": "gray32x16_pixels_gradients_hist_v1",
        },
        output / f"{task}_{region}_baseline.joblib",
    )
    (output / f"{task}_{region}_metrics.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a CPU baseline on prepared VR face regions")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="models/trained")
    parser.add_argument("--task", default="expression")
    parser.add_argument("--region", choices=("upper_face", "lower_face"), required=True)
    args = parser.parse_args()
    result = train(args.manifest, args.output, task=args.task, region=args.region)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
