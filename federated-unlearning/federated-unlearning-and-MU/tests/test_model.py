import torch

from src.models.cnn import build_model, count_parameters, model_size_bytes


def test_forward_pass_shape():
    model = build_model()
    x = torch.randn(4, 1, 28, 28)
    logits = model(x)
    assert logits.shape == (4, 10)


def test_checkpoint_save_load_roundtrip(tmp_path):
    from src.utils.checkpoint import load_checkpoint, save_checkpoint

    model = build_model()
    path = tmp_path / "model.pt"
    save_checkpoint(model, path, extra={"round": 1})

    model2 = build_model()
    payload = load_checkpoint(model2, path)

    assert payload["round"] == 1
    for p1, p2 in zip(model.parameters(), model2.parameters()):
        assert torch.allclose(p1, p2)


def test_count_parameters_positive():
    model = build_model()
    assert count_parameters(model) > 0


def test_model_size_bytes_positive():
    model = build_model()
    assert model_size_bytes(model) > 0
