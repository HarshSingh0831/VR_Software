import pytest


torch = pytest.importorskip("torch")

from adaptive_vr.cnn import CompactFaceCNN, class_weights
from adaptive_vr.public_dataset import PublicDatasetRecord


def test_compact_cnn_shape_and_size():
    model = CompactFaceCNN(7)
    output = model(torch.zeros(2, 1, 48, 96))
    assert output.shape == (2, 7)
    assert sum(parameter.numel() for parameter in model.parameters()) < 150_000


def test_class_weights_are_capped_for_rare_labels():
    records = [
        PublicDatasetRecord("a", "1", "common", "upper_face", "s", "x", "expression", "train", "0"),
        PublicDatasetRecord("b", "2", "common", "upper_face", "s", "x", "expression", "train", "0"),
        PublicDatasetRecord("c", "3", "rare", "upper_face", "s", "x", "expression", "train", "1"),
    ]
    weights = class_weights(records, ["common", "rare"])
    assert weights.shape == (2,)
    assert float(weights.max()) <= 5.0
