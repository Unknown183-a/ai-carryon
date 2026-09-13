"""Shared data helpers: building per-client Subset/DataLoader objects."""
from __future__ import annotations

from typing import Dict, List


def build_client_loaders(dataset, partitions: Dict[int, List[int]], batch_size: int = 32, shuffle: bool = True):
    """Given a dataset and {client_id: [indices]}, return {client_id: DataLoader}."""
    from torch.utils.data import DataLoader, Subset

    loaders = {}
    for client_id, indices in partitions.items():
        subset = Subset(dataset, indices)
        loaders[client_id] = DataLoader(subset, batch_size=batch_size, shuffle=shuffle)
    return loaders


def exclude_client(partitions: Dict[int, List[int]], forget_client: int) -> Dict[int, List[int]]:
    """Return a copy of `partitions` with `forget_client` removed (used by the
    full-retraining baseline, blueprint §12)."""
    return {cid: idx for cid, idx in partitions.items() if cid != forget_client}
