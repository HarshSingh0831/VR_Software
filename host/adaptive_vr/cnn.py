from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import random
import time

import numpy as np
from PIL import Image, ImageOps
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .public_dataset import PublicDatasetRecord, read_public_manifest


@dataclass(frozen=True, slots=True)
class CnnConfig:
    image_width: int = 96
    image_height: int = 48
    batch_size: int = 128
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    epochs: int = 12
    patience: int = 3
    seed: int = 42


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class ManifestImageDataset(Dataset[tuple[torch.Tensor, int]]):
    def __init__(
        self,
        records: list[PublicDatasetRecord],
        root: Path,
        classes: list[str],
        *,
        augment: bool,
    ):
        self.records = records
        self.root = root
        self.class_to_index = {label: index for index, label in enumerate(classes)}
        self.augment = augment
        self.images = np.empty((len(records), 48, 96), dtype=np.uint8)
        for index, record in enumerate(records):
            with Image.open(self.root / record.path) as source:
                image = ImageOps.grayscale(source).resize((96, 48), Image.Resampling.BILINEAR)
                self.images[index] = np.asarray(image, dtype=np.uint8)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        record = self.records[index]
        pixels = self.images[index].astype(np.float32) / 255.0
        tensor = torch.from_numpy(pixels).unsqueeze(0)
        if self.augment:
            if random.random() < 0.5:
                tensor = torch.flip(tensor, dims=(2,))
            tensor = torch.clamp(tensor * random.uniform(0.85, 1.15), 0.0, 1.0)
            mean = tensor.mean()
            tensor = torch.clamp(
                (tensor - mean) * random.uniform(0.85, 1.15) + mean, 0.0, 1.0
            )
            if random.random() < 0.35:
                translate_x = random.randint(-4, 4)
                translate_y = random.randint(-2, 2)
                tensor = torch.roll(tensor, shifts=(translate_y, translate_x), dims=(1, 2))
                if translate_y > 0:
                    tensor[:, :translate_y, :] = 0
                elif translate_y < 0:
                    tensor[:, translate_y:, :] = 0
                if translate_x > 0:
                    tensor[:, :, :translate_x] = 0
                elif translate_x < 0:
                    tensor[:, :, translate_x:] = 0
        tensor = (tensor - 0.5) / 0.5
        return tensor, self.class_to_index[record.label]


def _separable_block(in_channels: int, out_channels: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(
            in_channels, in_channels, 3, padding=1, groups=in_channels, bias=False
        ),
        nn.BatchNorm2d(in_channels),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels, out_channels, 1, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(2),
    )


class CompactFaceCNN(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 5, stride=2, padding=2, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            _separable_block(16, 32),
            _separable_block(32, 64),
            _separable_block(64, 96),
        )
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.25),
            nn.Linear(96, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.25),
            nn.Linear(64, num_classes),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(images))


def records_for(
    records: list[PublicDatasetRecord], *, task: str, region: str, split: str
) -> list[PublicDatasetRecord]:
    return [
        record
        for record in records
        if record.task == task and record.region == region and record.split == split
    ]


def class_weights(records: list[PublicDatasetRecord], classes: list[str]) -> torch.Tensor:
    counts = Counter(record.label for record in records)
    total = sum(counts.values())
    weights = [min(5.0, total / (len(classes) * counts[label])) for label in classes]
    return torch.tensor(weights, dtype=torch.float32)


def make_loader(
    records: list[PublicDatasetRecord],
    root: Path,
    classes: list[str],
    *,
    batch_size: int,
    augment: bool,
    shuffle: bool,
) -> DataLoader[tuple[torch.Tensor, torch.Tensor]]:
    return DataLoader(
        ManifestImageDataset(records, root, classes, augment=augment),
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=False,
    )


def evaluate(
    model: nn.Module,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    criterion: nn.Module,
    device: torch.device,
) -> tuple[dict[str, object], np.ndarray]:
    model.eval()
    losses: list[float] = []
    truth: list[int] = []
    predicted: list[int] = []
    probabilities: list[np.ndarray] = []
    with torch.inference_mode():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            losses.append(float(criterion(logits, labels).item()))
            probability = torch.softmax(logits, dim=1)
            probabilities.append(probability.cpu().numpy())
            truth.extend(labels.cpu().tolist())
            predicted.extend(probability.argmax(dim=1).cpu().tolist())
    result: dict[str, object] = {
        "loss": float(np.mean(losses)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1": float(f1_score(truth, predicted, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(truth, predicted).tolist(),
    }
    return result, np.concatenate(probabilities)


def train_region(
    manifest: str | Path,
    output: str | Path,
    *,
    task: str,
    region: str,
    config: CnnConfig,
    limit: int | None = None,
) -> dict[str, object]:
    seed_everything(config.seed)
    torch.set_num_threads(max(1, min(6, os.cpu_count() or 1)))
    manifest = Path(manifest)
    records = read_public_manifest(manifest)
    train_records = records_for(records, task=task, region=region, split="train")
    validation_records = records_for(records, task=task, region=region, split="validation")
    if limit:
        train_records = train_records[:limit]
        validation_records = validation_records[: max(128, limit // 5)]
    classes = sorted({record.label for record in train_records})
    if len(classes) < 2 or not validation_records:
        raise ValueError("Training requires at least two classes and a validation split")
    root = manifest.parent
    train_loader = make_loader(
        train_records, root, classes, batch_size=config.batch_size, augment=True, shuffle=True
    )
    validation_loader = make_loader(
        validation_records,
        root,
        classes,
        batch_size=config.batch_size,
        augment=False,
        shuffle=False,
    )
    device = torch.device("cpu")
    model = CompactFaceCNN(len(classes)).to(device)
    weights = class_weights(train_records, classes).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=1
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / f"{task}_{region}_cnn.pt"
    history: list[dict[str, object]] = []
    best_f1 = -1.0
    stale_epochs = 0
    started = time.time()

    for epoch in range(1, config.epochs + 1):
        model.train()
        train_loss: list[float] = []
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_loss.append(float(loss.item()))
        validation, _ = evaluate(model, validation_loader, criterion, device)
        scheduler.step(float(validation["macro_f1"]))
        epoch_result: dict[str, object] = {
            "epoch": epoch,
            "train_loss": float(np.mean(train_loss)),
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            **{f"validation_{key}": value for key, value in validation.items()},
        }
        history.append(epoch_result)
        print(json.dumps(epoch_result), flush=True)
        if float(validation["macro_f1"]) > best_f1 + 1e-4:
            best_f1 = float(validation["macro_f1"])
            stale_epochs = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "classes": classes,
                    "task": task,
                    "region": region,
                    "config": asdict(config),
                    "validation": validation,
                },
                checkpoint_path,
            )
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                break

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    scripted = torch.jit.trace(model, torch.zeros(1, 1, 48, 96))
    scripted.save(str(output / f"{task}_{region}_cnn_scripted.pt"))
    result: dict[str, object] = {
        "task": task,
        "region": region,
        "classes": classes,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_samples": len(train_records),
        "validation_samples": len(validation_records),
        "best_validation_macro_f1": best_f1,
        "epochs_completed": len(history),
        "training_seconds": round(time.time() - started, 2),
        "history": history,
    }
    (output / f"{task}_{region}_cnn_history.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def load_checkpoint(path: Path) -> tuple[CompactFaceCNN, list[str], dict[str, object]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    classes = list(checkpoint["classes"])
    model = CompactFaceCNN(len(classes))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, classes, checkpoint


def evaluate_two_camera(
    manifest: str | Path,
    model_dir: str | Path,
    *,
    task: str,
    split: str,
    batch_size: int = 256,
) -> dict[str, object]:
    manifest = Path(manifest)
    model_dir = Path(model_dir)
    all_records = read_public_manifest(manifest)
    upper_records = sorted(
        records_for(all_records, task=task, region="upper_face", split=split),
        key=lambda row: row.subject_id,
    )
    lower_records = sorted(
        records_for(all_records, task=task, region="lower_face", split=split),
        key=lambda row: row.subject_id,
    )
    if len(upper_records) != len(lower_records) or not upper_records:
        raise ValueError("Upper and lower camera records are not paired")
    if any(
        upper.subject_id != lower.subject_id or upper.label != lower.label
        for upper, lower in zip(upper_records, lower_records, strict=True)
    ):
        raise ValueError("Upper and lower camera record ordering does not match")
    upper_model, classes, _ = load_checkpoint(model_dir / f"{task}_upper_face_cnn.pt")
    lower_model, lower_classes, _ = load_checkpoint(model_dir / f"{task}_lower_face_cnn.pt")
    if classes != lower_classes:
        raise ValueError("CNN class order differs between cameras")
    criterion = nn.CrossEntropyLoss()
    upper_loader = make_loader(
        upper_records, manifest.parent, classes, batch_size=batch_size, augment=False, shuffle=False
    )
    lower_loader = make_loader(
        lower_records, manifest.parent, classes, batch_size=batch_size, augment=False, shuffle=False
    )
    upper_metrics, upper_probability = evaluate(
        upper_model, upper_loader, criterion, torch.device("cpu")
    )
    lower_metrics, lower_probability = evaluate(
        lower_model, lower_loader, criterion, torch.device("cpu")
    )
    truth = np.asarray([classes.index(record.label) for record in upper_records])
    fused_probability = (upper_probability + lower_probability) / 2.0
    fused_prediction = fused_probability.argmax(axis=1)
    fusion_metrics: dict[str, object] = {
        "accuracy": float(accuracy_score(truth, fused_prediction)),
        "macro_f1": float(f1_score(truth, fused_prediction, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(truth, fused_prediction).tolist(),
    }
    result: dict[str, object] = {
        "task": task,
        "split": split,
        "samples": len(truth),
        "classes": classes,
        "upper_face": upper_metrics,
        "lower_face": lower_metrics,
        "equal_probability_fusion": fusion_metrics,
    }
    (model_dir / f"{task}_{split}_cnn_fusion_metrics.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate compact partial-face CNNs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--manifest", required=True)
    train_parser.add_argument("--output", default="models/cnn")
    train_parser.add_argument("--task", default="expression")
    train_parser.add_argument("--region", choices=("upper_face", "lower_face"), required=True)
    train_parser.add_argument("--epochs", type=int, default=12)
    train_parser.add_argument("--patience", type=int, default=3)
    train_parser.add_argument("--batch-size", type=int, default=128)
    train_parser.add_argument("--limit", type=int)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--manifest", required=True)
    evaluate_parser.add_argument("--model-dir", default="models/cnn")
    evaluate_parser.add_argument("--task", default="expression")
    evaluate_parser.add_argument("--split", choices=("validation", "test"), default="test")
    args = parser.parse_args()

    if args.command == "train":
        config = CnnConfig(epochs=args.epochs, patience=args.patience, batch_size=args.batch_size)
        print(
            json.dumps(
                train_region(
                    args.manifest,
                    args.output,
                    task=args.task,
                    region=args.region,
                    config=config,
                    limit=args.limit,
                ),
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                evaluate_two_camera(
                    args.manifest,
                    args.model_dir,
                    task=args.task,
                    split=args.split,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
