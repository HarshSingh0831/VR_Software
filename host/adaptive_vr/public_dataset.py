from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


FER2013_LABELS = {
    0: "angry",
    1: "disgust",
    2: "fear",
    3: "happy",
    4: "sad",
    5: "surprise",
    6: "neutral",
}
FER2013_SPLITS = {
    "Training": "train",
    "PublicTest": "validation",
    "PrivateTest": "test",
    "train": "train",
    "validation": "validation",
    "test": "test",
}
MANIFEST_FIELDS = (
    "path",
    "subject_id",
    "label",
    "region",
    "session_id",
    "source",
    "task",
    "split",
    "original_label",
)


@dataclass(frozen=True, slots=True)
class PublicDatasetRecord:
    path: str
    subject_id: str
    label: str
    region: str
    session_id: str
    source: str
    task: str
    split: str
    original_label: str


def _normalized_face(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    return ImageOps.fit(grayscale, (96, 96), method=Image.Resampling.BILINEAR)


def vr_region_crops(image: Image.Image) -> dict[str, Image.Image]:
    """Create the two grayscale views available inside the VR headset."""
    face = _normalized_face(image)
    upper = ImageOps.fit(face.crop((0, 12, 96, 57)), (96, 48), Image.Resampling.BILINEAR)
    lower = ImageOps.fit(face.crop((0, 48, 96, 96)), (96, 48), Image.Resampling.BILINEAR)
    return {"upper_face": upper, "lower_face": lower}


def _pixels_to_image(pixels: str) -> Image.Image:
    values = bytes(int(value) for value in pixels.split())
    if len(values) != 48 * 48:
        raise ValueError(f"FER2013 row has {len(values)} pixels; expected 2304")
    return Image.frombytes("L", (48, 48), values)


def write_manifest(records: Iterable[PublicDatasetRecord], path: str | Path) -> int:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
            count += 1
    return count


def read_public_manifest(path: str | Path) -> list[PublicDatasetRecord]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(MANIFEST_FIELDS).difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Manifest missing columns: {', '.join(sorted(missing))}")
        return [PublicDatasetRecord(**{field: row[field] for field in MANIFEST_FIELDS}) for row in reader]


def prepare_fer2013(
    csv_path: str | Path,
    output_root: str | Path,
    *,
    limit: int | None = None,
) -> list[PublicDatasetRecord]:
    """Convert the canonical FER2013 pixel CSV into VR upper/lower crops."""
    csv_path = Path(csv_path)
    output_root = Path(output_root)
    image_root = output_root / "images"
    records: list[PublicDatasetRecord] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"emotion", "pixels", "Usage"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"FER2013 CSV missing columns: {', '.join(sorted(missing))}")
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                break
            label_code = int(row["emotion"])
            if label_code not in FER2013_LABELS:
                continue
            label = FER2013_LABELS[label_code]
            split = FER2013_SPLITS.get(row["Usage"], row["Usage"].lower())
            sample_id = f"fer2013_{index:06d}"
            for region, crop in vr_region_crops(_pixels_to_image(row["pixels"])).items():
                relative = Path("images") / split / region / label / f"{sample_id}.pgm"
                destination = output_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                crop.save(destination, format="PPM")
                records.append(
                    PublicDatasetRecord(
                        path=relative.as_posix(),
                        subject_id=sample_id,
                        label=label,
                        region=region,
                        session_id="fer2013",
                        source="FER2013",
                        task="expression",
                        split=split,
                        original_label=str(label_code),
                    )
                )
    write_manifest(records, output_root / "manifest.csv")
    return records


def _parquet_split(path: Path) -> str:
    name = path.name.lower()
    if "train" in name:
        return "train"
    if "valid" in name:
        return "validation"
    if "test" in name:
        return "test"
    raise ValueError(f"Cannot infer train/validation/test split from {path.name}")


def prepare_fer2013_parquet(
    parquet_paths: Iterable[str | Path],
    output_root: str | Path,
    *,
    limit_per_split: int | None = None,
) -> list[PublicDatasetRecord]:
    """Convert Hugging Face-style FER2013 Parquet shards without loading all rows."""
    import pyarrow.parquet as parquet

    output_root = Path(output_root)
    records: list[PublicDatasetRecord] = []
    global_index = 0
    for raw_path in parquet_paths:
        parquet_path = Path(raw_path)
        split = _parquet_split(parquet_path)
        split_index = 0
        source = parquet.ParquetFile(parquet_path)
        for batch in source.iter_batches(batch_size=512, columns=["label", "image"]):
            for row in batch.to_pylist():
                if limit_per_split is not None and split_index >= limit_per_split:
                    break
                label_code = int(row["label"])
                image_data = row["image"]
                if label_code not in FER2013_LABELS or not image_data or not image_data.get("bytes"):
                    continue
                label = FER2013_LABELS[label_code]
                sample_id = f"fer2013_{global_index:06d}"
                with Image.open(BytesIO(image_data["bytes"])) as image:
                    crops = vr_region_crops(image)
                for region, crop in crops.items():
                    relative = Path("images") / split / region / label / f"{sample_id}.pgm"
                    destination = output_root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    crop.save(destination, format="PPM")
                    records.append(
                        PublicDatasetRecord(
                            path=relative.as_posix(),
                            subject_id=sample_id,
                            label=label,
                            region=region,
                            session_id="fer2013",
                            source="FER2013",
                            task="expression",
                            split=split,
                            original_label=str(label_code),
                        )
                    )
                split_index += 1
                global_index += 1
            if limit_per_split is not None and split_index >= limit_per_split:
                break
    write_manifest(records, output_root / "manifest.csv")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare public face datasets for VR camera training")
    subparsers = parser.add_subparsers(dest="dataset", required=True)
    fer = subparsers.add_parser("fer2013", help="Convert a canonical fer2013.csv file")
    fer.add_argument("--csv", required=True)
    fer.add_argument("--output", default="models/datasets/fer2013_vr")
    fer.add_argument("--limit", type=int)
    fer_parquet = subparsers.add_parser(
        "fer2013-parquet", help="Convert FER2013 Parquet train/validation/test shards"
    )
    fer_parquet.add_argument("--input", action="append", required=True)
    fer_parquet.add_argument("--output", default="models/datasets/fer2013_vr")
    fer_parquet.add_argument("--limit-per-split", type=int)
    args = parser.parse_args()

    if args.dataset == "fer2013":
        records = prepare_fer2013(args.csv, args.output, limit=args.limit)
        print(f"Prepared {len(records)} region images in {args.output}")
    elif args.dataset == "fer2013-parquet":
        records = prepare_fer2013_parquet(
            args.input, args.output, limit_per_split=args.limit_per_split
        )
        print(f"Prepared {len(records)} region images in {args.output}")


if __name__ == "__main__":
    main()
