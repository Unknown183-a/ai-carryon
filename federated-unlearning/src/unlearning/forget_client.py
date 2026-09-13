"""Forget-client selection utilities.

STATUS: scaffold. Selecting a forget client is trivial once client
partitions exist; kept as its own module so selection logic (e.g.
random vs. targeted vs. worst-case client selection for later
experiments) stays decoupled from the unlearning engine itself.
"""
from __future__ import annotations

from typing import Dict

from torch.utils.data import Subset


def select_forget_client(client_datasets: Dict[int, Subset], client_id: int) -> Subset:
    if client_id not in client_datasets:
        raise ValueError(f"client_id {client_id} not found among {list(client_datasets)}")
    return client_datasets[client_id]


def remaining_clients(client_datasets: Dict[int, Subset], forget_client_id: int) -> Dict[int, Subset]:
    return {cid: ds for cid, ds in client_datasets.items() if cid != forget_client_id}
