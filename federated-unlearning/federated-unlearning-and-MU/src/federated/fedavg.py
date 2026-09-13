"""
FedAvg aggregation (blueprint §8):

    W_{t+1} = sum_k (n_k / n) * W_{t+1}^{(k)}

i.e. a weighted average of client parameters, weighted by each client's
local dataset size.
"""
from __future__ import annotations

from typing import List

from src.federated.client import ClientUpdateResult


def federated_average(client_results: List[ClientUpdateResult]) -> dict:
    """Compute the sample-size-weighted average of client state_dicts."""
    import torch

    total_samples = sum(r.num_samples for r in client_results)
    if total_samples == 0:
        raise ValueError("Total number of samples across clients is zero.")

    avg_state = None
    for result in client_results:
        weight = result.num_samples / total_samples
        if avg_state is None:
            avg_state = {k: v.clone().float() * weight for k, v in result.state_dict.items()}
        else:
            for k, v in result.state_dict.items():
                avg_state[k] += v.float() * weight

    # Cast back to original dtypes (e.g. some buffers may be int/long).
    reference = client_results[0].state_dict
    for k in avg_state:
        avg_state[k] = avg_state[k].to(reference[k].dtype)

    return avg_state
