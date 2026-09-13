"""Full-retraining baseline: gold-standard reference for unlearning quality.

STATUS: scaffold. Mechanically this is "run the same FL loop
(src/federated/server.py) on the client set with the forget client
removed" — the runner below will wire that up in Phase 3. Not yet
exposed as a CLI/experiment script.
"""
from __future__ import annotations

from typing import Any, Dict

import torch.nn as nn


def run_full_retraining(
    client_datasets: Dict[int, Any],
    forget_client_id: int,
    model_factory,
    config: Dict[str, Any],
) -> nn.Module:
    raise NotImplementedError(
        "run_full_retraining is a scaffold for Phase 3 (docs/roadmap.md). "
        "It will remove forget_client_id from client_datasets and reuse "
        "src/federated/server.py::FederatedServer to train M_retrain from "
        "scratch, for a fair comparison against M_unlearn."
    )
