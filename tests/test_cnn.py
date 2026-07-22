import pytest


torch = pytest.importorskip("torch")

from adaptive_vr.cnn import CompactFaceCNN, class_weights, transfer_compatible_weights
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


def test_transfer_reuses_features_but_keeps_new_twelve_class_head(tmp_path):
    source = CompactFaceCNN(7)
    with torch.no_grad():
        source.features[0].weight.fill_(0.25)
        source.classifier[3].weight.fill_(0.5)
        source.classifier[6].weight.fill_(0.75)
    checkpoint = tmp_path / "expression_upper_face_cnn.pt"
    torch.save(
        {
            "state_dict": source.state_dict(),
            "classes": [str(index) for index in range(7)],
            "task": "expression",
            "region": "upper_face",
        },
        checkpoint,
    )

    target = CompactFaceCNN(12)
    original_head = target.classifier[6].weight.detach().clone()
    transferred = transfer_compatible_weights(
        target, checkpoint, expected_region="upper_face"
    )

    assert "features.0.weight" in transferred
    assert "classifier.3.weight" in transferred
    assert "classifier.6.weight" not in transferred
    assert torch.all(target.features[0].weight == 0.25)
    assert torch.all(target.classifier[3].weight == 0.5)
    assert torch.equal(target.classifier[6].weight, original_head)
    assert target(torch.zeros(2, 1, 48, 96)).shape == (2, 12)


def test_transfer_rejects_the_wrong_camera_region(tmp_path):
    checkpoint = tmp_path / "lower.pt"
    source = CompactFaceCNN(7)
    torch.save(
        {"state_dict": source.state_dict(), "region": "lower_face"}, checkpoint
    )
    with pytest.raises(ValueError, match="Checkpoint region"):
        transfer_compatible_weights(
            CompactFaceCNN(12), checkpoint, expected_region="upper_face"
        )
