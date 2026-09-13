import torch
from torch.utils.data import TensorDataset

from src.data.partition import iid_partition, non_iid_dirichlet_partition


def _toy_dataset(n=100, num_classes=10):
    x = torch.randn(n, 1, 28, 28)
    y = torch.randint(0, num_classes, (n,))
    return TensorDataset(x, y)


def test_iid_partition_covers_all_samples():
    ds = _toy_dataset(100)
    parts = iid_partition(ds, num_clients=5, seed=0)
    total = sum(len(p) for p in parts.values())
    assert total == 100
    assert len(parts) == 5


def test_non_iid_partition_covers_all_samples():
    ds = _toy_dataset(200)
    parts = non_iid_dirichlet_partition(ds, num_clients=4, alpha=0.5, seed=0)
    total = sum(len(p) for p in parts.values())
    assert total == 200
    assert len(parts) == 4
