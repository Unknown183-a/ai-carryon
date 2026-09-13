"""Federated server: orchestrates rounds, selects clients, aggregates, checkpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn

from src.utils.checkpoint import save_checkpoint
from src.utils.logging import get_logger

from .client import FederatedClient
from .fedavg import fedavg
from .round_manager import RoundManager


class FederatedServer:
    def __init__(
        self,
        global_model: nn.Module,
        clients: Dict[int, FederatedClient],
        artifacts_dir: str | Path,
        save_every_n_rounds: int = 5,
    ):
        self.global_model = global_model
        self.clients = clients
        self.artifacts_dir = Path(artifacts_dir)
        self.save_every_n_rounds = save_every_n_rounds
        self.round_manager = RoundManager()
        self.logger = get_logger("federated.server", self.artifacts_dir / "training.log")

    def run(self, num_rounds: int, local_epochs: int, local_lr: float, test_client: FederatedClient | None = None):
        for round_num in range(1, num_rounds + 1):
            updates = [
                client.local_train(self.global_model, epochs=local_epochs, lr=local_lr)
                for client in self.clients.values()
            ]
            new_state = fedavg(updates)
            self.global_model.load_state_dict(new_state)

            avg_train_loss = sum(u.train_loss for u in updates) / len(updates)
            metrics = {"avg_train_loss": avg_train_loss}
            if test_client is not None:
                metrics.update({f"test_{k}": v for k, v in test_client.evaluate(self.global_model).items()})

            self.round_manager.record(round_num, **metrics)
            self.logger.info("Round %d/%d: %s", round_num, num_rounds, metrics)

            if round_num % self.save_every_n_rounds == 0 or round_num == num_rounds:
                ckpt_path = self.artifacts_dir / "checkpoints" / f"round_{round_num:03d}.pt"
                save_checkpoint(self.global_model, ckpt_path, extra={"round": round_num, "metrics": metrics})

        self.round_manager.save_csv(self.artifacts_dir / "metrics.csv")
        return self.global_model
