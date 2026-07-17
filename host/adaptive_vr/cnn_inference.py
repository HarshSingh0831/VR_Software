from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import torch


@dataclass(frozen=True, slots=True)
class CnnPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def _preprocess(source: Image.Image) -> torch.Tensor:
    image = ImageOps.grayscale(source).resize((96, 48), Image.Resampling.BILINEAR)
    pixels = np.asarray(image, dtype=np.float32).copy() / 255.0
    tensor = torch.from_numpy(pixels).unsqueeze(0).unsqueeze(0)
    return (tensor - 0.5) / 0.5


def preprocess_image(path: str | Path) -> torch.Tensor:
    with Image.open(path) as source:
        return _preprocess(source)


def preprocess_bytes(data: bytes) -> torch.Tensor:
    with Image.open(BytesIO(data)) as source:
        return _preprocess(source)


class PartialFaceCnnPredictor:
    def __init__(self, model_dir: str | Path, *, task: str = "expression"):
        model_dir = Path(model_dir)
        self.upper = torch.jit.load(str(model_dir / f"{task}_upper_face_cnn_scripted.pt"))
        self.lower = torch.jit.load(str(model_dir / f"{task}_lower_face_cnn_scripted.pt"))
        checkpoint = torch.load(
            model_dir / f"{task}_upper_face_cnn.pt", map_location="cpu", weights_only=True
        )
        self.classes = list(checkpoint["classes"])
        self.upper.eval()
        self.lower.eval()

    def _result(self, probability: torch.Tensor) -> CnnPrediction:
        values = probability.squeeze(0).cpu().tolist()
        index = int(probability.argmax(dim=1).item())
        return CnnPrediction(
            label=self.classes[index],
            confidence=float(values[index]),
            probabilities=dict(zip(self.classes, (float(value) for value in values), strict=True)),
        )

    def predict(self, upper_path: str | Path, lower_path: str | Path) -> dict[str, CnnPrediction]:
        return self._predict_tensors(preprocess_image(upper_path), preprocess_image(lower_path))

    def predict_bytes(self, upper: bytes, lower: bytes) -> dict[str, CnnPrediction]:
        return self._predict_tensors(preprocess_bytes(upper), preprocess_bytes(lower))

    def _predict_tensors(
        self, upper_image: torch.Tensor, lower_image: torch.Tensor
    ) -> dict[str, CnnPrediction]:
        with torch.inference_mode():
            upper_probability = torch.softmax(self.upper(upper_image), dim=1)
            lower_probability = torch.softmax(self.lower(lower_image), dim=1)
            fused_probability = (upper_probability + lower_probability) / 2.0
        return {
            "upper_face": self._result(upper_probability),
            "lower_face": self._result(lower_probability),
            "fused": self._result(fused_probability),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the two-camera CNN on synchronized images")
    parser.add_argument("--model-dir", default="models/cnn")
    parser.add_argument("--task", default="expression")
    parser.add_argument("--upper", required=True)
    parser.add_argument("--lower", required=True)
    args = parser.parse_args()
    predictor = PartialFaceCnnPredictor(args.model_dir, task=args.task)
    predictions = predictor.predict(args.upper, args.lower)
    print(
        json.dumps(
            {
                region: {
                    "label": prediction.label,
                    "confidence": prediction.confidence,
                    "probabilities": prediction.probabilities,
                }
                for region, prediction in predictions.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
