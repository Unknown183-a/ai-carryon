from torch.utils.data import DataLoader

from src.unlearning.forget_client import select_forget_client, split_forget_and_remaining
from src.unlearning.gradient_ascent import GradientAscentUnlearner
from src.unlearning.knowledge_distillation import KnowledgeDistiller
from src.models.cnn import build_model


def test_select_forget_client_from_config():
    cfg = {"unlearning": {"forget_client": 2}}
    assert select_forget_client(cfg) == 2


def test_select_forget_client_missing_raises():
    import pytest

    with pytest.raises(ValueError):
        select_forget_client({"unlearning": {}})


def test_split_forget_and_remaining():
    partitions = {0: [1, 2], 1: [3, 4], 2: [5, 6]}
    forget_idx, remaining = split_forget_and_remaining(partitions, forget_client=1)
    assert forget_idx == [3, 4]
    assert remaining == {0: [1, 2], 2: [5, 6]}


def test_gradient_ascent_runs_and_returns_valid_model(tiny_dataset):
    loader = DataLoader(tiny_dataset, batch_size=16)
    model = build_model()
    unlearner = GradientAscentUnlearner(model, {"learning_rate": 0.001, "epochs": 1})

    result = unlearner.unlearn(loader)

    assert result.epochs_run == 1
    assert result.final_forget_loss == result.final_forget_loss  # not NaN
    # returned state_dict loads cleanly into a fresh model
    fresh = build_model()
    fresh.load_state_dict(result.state_dict)


def test_kd_loss_runs_and_returns_valid_model(tiny_dataset):
    loader = DataLoader(tiny_dataset, batch_size=16)
    teacher = build_model()
    student = build_model()
    distiller = KnowledgeDistiller(student, teacher, {"learning_rate": 0.01, "epochs": 1, "temperature": 4.0})

    result = distiller.distill(loader)

    assert result.epochs_run == 1
    fresh = build_model()
    fresh.load_state_dict(result.state_dict)
