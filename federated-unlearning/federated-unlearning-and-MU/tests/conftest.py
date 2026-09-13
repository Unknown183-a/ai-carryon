"""Shared pytest fixtures: a tiny synthetic dataset so tests run fast and
without needing to download MNIST."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _TinyDataset:
    """Minimal MNIST-like dataset: random 28x28 images, labels 0-9."""

    def __init__(self, n=200, seed=0):
        rng = np.random.default_rng(seed)
        self.data_x = rng.standard_normal((n, 1, 28, 28)).astype("float32")
        self.targets = rng.integers(0, 10, size=n).tolist()

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        import torch

        return torch.tensor(self.data_x[idx]), self.targets[idx]


@pytest.fixture
def tiny_dataset():
    return _TinyDataset()
