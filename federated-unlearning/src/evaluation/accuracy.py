"""Overall / per-client accuracy evaluation.

This is implemented and usable now (it only depends on the FL client's
evaluate() method, already working in Phase 2).
"""
from __future__ import annotations

from typing import Dict

import torch.nn as nn

from src.federated.client import FederatedClient


def evaluate_overall(model: nn.Module, test_client: FederatedClient) -> Dict[str, float]:
    """Accuracy/loss on the global held-out test set."""
    return test_client.evaluate(model)


def evaluate_per_client(model: nn.Module, clients: Dict[int, FederatedClient]) -> Dict[int, Dict[str, float]]:
    return {cid: client.evaluate(model) for cid, client in clients.items()}
