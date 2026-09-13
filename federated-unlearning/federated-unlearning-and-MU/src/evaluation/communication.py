"""
Communication-cost measurement (blueprint §13.F): number of rounds, number
of model transmissions, and approximate bytes transferred.
"""
from __future__ import annotations

from typing import Dict


def communication_cost(num_rounds: int, num_clients: int, model) -> Dict[str, float]:
    """
    Approximate communication cost for a standard FedAvg run:
    each round, the server sends the global model to every client
    (download) and receives one update back from every client (upload).
    """
    from src.models.cnn import model_size_bytes

    per_model_bytes = model_size_bytes(model)
    transmissions_per_round = num_clients * 2  # download + upload per client
    total_transmissions = num_rounds * transmissions_per_round
    total_bytes = total_transmissions * per_model_bytes

    return {
        "num_rounds": num_rounds,
        "num_clients": num_clients,
        "model_size_bytes": per_model_bytes,
        "total_transmissions": total_transmissions,
        "approx_total_bytes": total_bytes,
        "approx_total_mb": round(total_bytes / (1024 ** 2), 3),
    }


def unlearning_communication_cost() -> Dict[str, float]:
    """
    Gradient Ascent + Knowledge Distillation as implemented here run
    LOCALLY on already-collected data (no client round-trips), so their
    direct communication cost is ~0 rounds. This is one of the expected
    efficiency advantages over full retraining (blueprint §2 Secondary
    Goals) and should be reported as such once measured.
    """
    return {"num_rounds": 0, "total_transmissions": 0, "approx_total_bytes": 0}
