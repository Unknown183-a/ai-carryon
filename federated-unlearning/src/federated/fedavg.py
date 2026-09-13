"""FedAvg aggregation: weighted average of client state dicts by sample count."""
from __future__ import annotations

from typing import Dict, List

import torch

from .client import ClientUpdate


def fedavg(updates: List[ClientUpdate]) -> Dict[str, torch.Tensor]:
    """Compute W_{t+1} = sum_k (n_k / n) * W_{t+1}^{(k)}."""
    total_samples = sum(u.num_samples for u in updates)
    if total_samples == 0:
        raise ValueError("Total sample count across client updates is zero.")

    avg_state: Dict[str, torch.Tensor] = {}
    for key in updates[0].state_dict:
        weighted_sum = torch.zeros_like(updates[0].state_dict[key], dtype=torch.float32)
        for update in updates:
            weight = update.num_samples / total_samples
            weighted_sum += weight * update.state_dict[key].float()
        avg_state[key] = weighted_sum.to(updates[0].state_dict[key].dtype)
    return avg_state
