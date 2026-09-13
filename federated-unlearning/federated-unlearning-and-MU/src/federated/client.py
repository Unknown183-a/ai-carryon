"""
FL client (Module C — blueprint §7, §8).

Responsibilities: hold a local dataset, receive the global model, train
locally for a configured number of epochs, evaluate, and return updated
parameters. Deliberately framework-agnostic (no Flower dependency) so the
core FL logic stays easy to read; a Flower-based `federated/flower_client.py`
could wrap this later without changing the core logic (blueprint instruction 7).
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class ClientUpdateResult:
    client_id: int
    state_dict: Dict
    num_samples: int
    train_loss: float
    train_accuracy: float
    train_time_seconds: float


class FederatedClient:
    def __init__(self, client_id: int, data_loader, device: str = "cpu"):
        self.client_id = client_id
        self.data_loader = data_loader
        self.device = device
        self.num_samples = len(data_loader.dataset)

    def local_train(self, global_model, local_epochs: int, lr: float, momentum: float = 0.9) -> ClientUpdateResult:
        """Train a local copy of `global_model` for `local_epochs` epochs
        on this client's data, then return the updated parameters."""
        import torch
        import torch.nn as nn
        import torch.optim as optim

        model = copy.deepcopy(global_model).to(self.device)
        model.train()

        optimizer = optim.SGD(model.parameters(), lr=lr, momentum=momentum)
        criterion = nn.CrossEntropyLoss()

        start = time.time()
        total_loss, correct, total = 0.0, 0, 0

        for _ in range(local_epochs):
            for x, y in self.data_loader:
                x, y = x.to(self.device), y.to(self.device)
                optimizer.zero_grad()
                logits = model(x)
                loss = criterion(logits, y)
                loss.backward()
                optimizer.step()

                total_loss += loss.item() * x.size(0)
                correct += (logits.argmax(dim=1) == y).sum().item()
                total += x.size(0)

        elapsed = time.time() - start
        avg_loss = total_loss / max(total, 1)
        accuracy = correct / max(total, 1)

        return ClientUpdateResult(
            client_id=self.client_id,
            state_dict=copy.deepcopy(model.state_dict()),
            num_samples=self.num_samples,
            train_loss=avg_loss,
            train_accuracy=accuracy,
            train_time_seconds=elapsed,
        )
