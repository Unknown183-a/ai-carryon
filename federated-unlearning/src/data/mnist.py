"""MNIST loading and normalization."""
from __future__ import annotations

from pathlib import Path

from torch.utils.data import Dataset
from torchvision import datasets, transforms

MNIST_MEAN = (0.1307,)
MNIST_STD = (0.3081,)


def get_mnist_datasets(data_dir: str | Path) -> tuple[Dataset, Dataset]:
    """Download (if needed) and return the MNIST train/test datasets, normalized."""
    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(MNIST_MEAN, MNIST_STD)]
    )
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    train_set = datasets.MNIST(root=str(data_dir), train=True, download=True, transform=transform)
    test_set = datasets.MNIST(root=str(data_dir), train=False, download=True, transform=transform)
    return train_set, test_set
