"""
Full-retraining baseline (blueprint §12) — the "gold standard" M_retrain
that the proposed GA+KD unlearning method is compared against.

Pipeline:
    Original Clients -> Remove Forget Client Ck -> Train FL from scratch -> M_retrain

Implemented by reusing the exact same FederatedServer / round_manager used
for the initial FL experiment, just called with the forget-client's loader
excluded — this guarantees a fair, apples-to-apples comparison (blueprint
§29 "Compare Fairly": same architecture, same training procedure).

STATUS: implemented, not yet executed. Running this trains a full new model
from scratch and is expected to be the most expensive baseline to compute
(blueprint §13.E computation-cost tracking applies here in particular).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.data.utils import exclude_client
from src.federated.client import FederatedClient
from src.federated.round_manager import run_federated_training
from src.federated.server import FederatedServer


def run_full_retraining_baseline(
    fresh_model,
    client_loaders: Dict[int, "DataLoader"],
    forget_client: int,
    test_loader,
    rounds: int,
    local_epochs: int,
    lr: float,
    momentum: float,
    output_dir: str | Path,
    device: str = "cpu",
) -> Dict:
    """Train a fresh global model from scratch on all clients EXCEPT `forget_client`."""
    remaining_loaders = {cid: loader for cid, loader in client_loaders.items() if cid != forget_client}

    clients: List[FederatedClient] = [
        FederatedClient(client_id=cid, data_loader=loader, device=device)
        for cid, loader in remaining_loaders.items()
    ]

    server = FederatedServer(fresh_model, clients, device=device)

    return run_federated_training(
        server=server,
        test_loader=test_loader,
        rounds=rounds,
        local_epochs=local_epochs,
        lr=lr,
        momentum=momentum,
        output_dir=output_dir,
        run_name="full_retraining_baseline",
    )
