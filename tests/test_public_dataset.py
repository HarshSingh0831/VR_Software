import csv

from PIL import Image

from adaptive_vr.public_dataset import (
    prepare_fer2013,
    prepare_fer2013_parquet,
    read_public_manifest,
    vr_region_crops,
)


def test_vr_region_crops_are_grayscale_and_camera_sized():
    image = Image.new("RGB", (48, 48), (10, 20, 30))
    crops = vr_region_crops(image)
    assert set(crops) == {"upper_face", "lower_face"}
    assert all(crop.mode == "L" and crop.size == (96, 48) for crop in crops.values())


def test_prepare_fer2013_writes_two_regions_per_row(tmp_path):
    source = tmp_path / "fer2013.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["emotion", "pixels", "Usage"])
        writer.writeheader()
        writer.writerow({"emotion": "3", "pixels": " ".join(["128"] * 2304), "Usage": "Training"})
    output = tmp_path / "prepared"
    records = prepare_fer2013(source, output)
    assert len(records) == 2
    assert {record.region for record in records} == {"upper_face", "lower_face"}
    assert all(record.label == "happy" and record.task == "expression" for record in records)
    loaded = read_public_manifest(output / "manifest.csv")
    assert loaded == records
    assert all((output / record.path).exists() for record in records)


def test_prepare_fer2013_parquet_streams_image_bytes(tmp_path):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    image_bytes = io.BytesIO()
    Image.new("L", (48, 48), 100).save(image_bytes, format="PNG")
    table = pa.Table.from_pylist(
        [{"label": 6, "image": {"bytes": image_bytes.getvalue(), "path": None}}]
    )
    source = tmp_path / "train.parquet"
    pq.write_table(table, source)
    records = prepare_fer2013_parquet([source], tmp_path / "prepared")
    assert len(records) == 2
    assert all(record.label == "neutral" and record.split == "train" for record in records)
