from pathlib import Path

from PIL import Image
import pytest


pytest.importorskip("torch")

from adaptive_vr.cnn_inference import preprocess_bytes, preprocess_image


def test_preprocess_image_returns_normalized_camera_tensor(tmp_path: Path):
    path = tmp_path / "camera.pgm"
    Image.new("L", (20, 10), 255).save(path)
    tensor = preprocess_image(path)
    assert tuple(tensor.shape) == (1, 1, 48, 96)
    assert float(tensor.min()) == pytest.approx(1.0)
    assert float(tensor.max()) == pytest.approx(1.0)


def test_preprocess_bytes_accepts_dashboard_png():
    import io

    encoded = io.BytesIO()
    Image.new("L", (20, 10), 0).save(encoded, format="PNG")
    tensor = preprocess_bytes(encoded.getvalue())
    assert tuple(tensor.shape) == (1, 1, 48, 96)
    assert float(tensor.min()) == pytest.approx(-1.0)
