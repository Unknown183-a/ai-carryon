"""Communication-cost measurement: rounds, transmissions, approximate bytes."""
from __future__ import annotations

from typing import Dict

import torch.nn as nn


def model_size_bytes(model: nn.Module) -> int:
    return sum(p.numel() * p.element_size() for p in model.parameters())


def communication_cost(model: nn.Module, num_rounds: int, num_clients: int) -> Dict[str, int]:
    """Approximate bytes transferred: 2 directions (down+up) x rounds x clients x model size."""
    per_transmission = model_size_bytes(model)
    return {
        "model_size_bytes": per_transmission,
        "num_rounds": num_rounds,
        "num_clients": num_clients,
        "approx_total_bytes": per_transmission * 2 * num_rounds * num_clients,
    }
