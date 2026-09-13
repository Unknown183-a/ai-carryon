"""
MNIST loading and normalization (Module A — blueprint §7).

Downloads/loads MNIST via torchvision and applies standard normalization.
This module is intentionally dataset-specific; swapping in a different
dataset later (blueprint §28 "Future Extensions") means adding a sibling
module here (e.g. cifar10.py), not touching the federated/unlearning code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple


def get_mnist_datasets(data_dir: str | Path = "data/raw") -> Tuple["Dataset", "Dataset"]:
    """
    Return (train_dataset, test_dataset) for MNIST, normalized to
    mean=0.1307, std=0.3081 (standard MNIST statistics).
    """
    import torchvision
    from torchvision import transforms

    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,)),
        ]
    )

    train_dataset = torchvision.datasets.MNIST(
        root=str(data_dir), train=True, download=True, transform=transform
    )
    test_dataset = torchvision.datasets.MNIST(
        root=str(data_dir), train=False, download=True, transform=transform
    )
    return train_dataset, test_dataset


def get_test_loader(data_dir: str | Path = "data/raw", batch_size: int = 256):
    """Convenience loader for the full (global) MNIST test set."""
    from torch.utils.data import DataLoader

    _, test_dataset = get_mnist_datasets(data_dir)
    return DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
