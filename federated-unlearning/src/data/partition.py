"""Client partitioning: IID and Non-IID (Dirichlet) splits over a dataset."""
from __future__ import annotations

from typing import Dict, List

import numpy as np
from torch.utils.data import Dataset, Subset


def iid_partition(dataset: Dataset, num_clients: int, seed: int = 42) -> Dict[int, Subset]:
    """Split dataset indices uniformly at random across clients."""
    rng = np.random.default_rng(seed)
    indices = np.arange(len(dataset))
    rng.shuffle(indices)
    shards = np.array_split(indices, num_clients)
    return {cid: Subset(dataset, shard.tolist()) for cid, shard in enumerate(shards)}


def non_iid_dirichlet_partition(
    dataset: Dataset, num_clients: int, alpha: float = 0.5, seed: int = 42
) -> Dict[int, Subset]:
    """Split dataset by label using a Dirichlet(alpha) distribution per class.

    Lower alpha => more label skew per client. This produces a
    label-heterogeneous (non-IID) partition, distinct from `iid_partition`.
    """
    rng = np.random.default_rng(seed)
    labels = np.array([dataset[i][1] for i in range(len(dataset))])
    classes = np.unique(labels)

    client_indices: List[List[int]] = [[] for _ in range(num_clients)]
    for c in classes:
        class_idx = np.where(labels == c)[0]
        rng.shuffle(class_idx)
        proportions = rng.dirichlet(alpha=[alpha] * num_clients)
        split_points = (np.cumsum(proportions) * len(class_idx)).astype(int)[:-1]
        splits = np.split(class_idx, split_points)
        for cid, split in enumerate(splits):
            client_indices[cid].extend(split.tolist())

    return {cid: Subset(dataset, idx) for cid, idx in enumerate(client_indices)}


def partition_dataset(
    dataset: Dataset, num_clients: int, strategy: str = "iid", alpha: float = 0.5, seed: int = 42
) -> Dict[int, Subset]:
    if strategy == "iid":
        return iid_partition(dataset, num_clients, seed=seed)
    if strategy == "non_iid":
        return non_iid_dirichlet_partition(dataset, num_clients, alpha=alpha, seed=seed)
    raise ValueError(f"Unknown partition strategy: {strategy}")
