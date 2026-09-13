import torch

from src.models.cnn import build_model


def test_cnn_output_shape():
    model = build_model("cnn", num_classes=10)
    x = torch.randn(4, 1, 28, 28)
    out = model(x)
    assert out.shape == (4, 10)


def test_unknown_model_raises():
    try:
        build_model("does_not_exist")
        assert False, "expected ValueError"
    except ValueError:
        pass
