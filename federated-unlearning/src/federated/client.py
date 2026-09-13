"""Federated client: local training and evaluation on a private shard."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


@dataclass
class ClientUpdate:
    client_id: int
    state_dict: Dict[str, torch.Tensor]
    num_samples: int
    train_loss: float


class FederatedClient:
    """Holds one client's private data and knows how to train/eval locally."""

    def __init__(self, client_id: int, dataset: Dataset, batch_size: int = 32, device: str = "cpu"):
        self.client_id = client_id
        self.dataset = dataset
        self.batch_size = batch_size
        self.device = device

    def local_train(self, global_model: nn.Module, epochs: int, lr: float) -> ClientUpdate:
        """Train a local copy of the global model for `epochs` epochs and return the update."""
        model = copy.deepcopy(global_model).to(self.device)
        model.train()
        optimizer = torch.optim.SGD(model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        loader = DataLoader(self.dataset, batch_size=self.batch_size, shuffle=True)

        total_loss, num_batches = 0.0, 0
        for _ in range(epochs):
            for x, y in loader:
                x, y = x.to(self.device), y.to(self.device)
                optimizer.zero_grad()
                loss = criterion(model(x), y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                num_batches += 1

        avg_loss = total_loss / max(num_batches, 1)
        return ClientUpdate(
            client_id=self.client_id,
            state_dict=model.state_dict(),
            num_samples=len(self.dataset),
            train_loss=avg_loss,
        )

    @torch.no_grad()
    def evaluate(self, model: nn.Module) -> Dict[str, float]:
        model = model.to(self.device)
        model.eval()
        loader = DataLoader(self.dataset, batch_size=self.batch_size, shuffle=False)
        criterion = nn.CrossEntropyLoss()

        correct, total, total_loss = 0, 0, 0.0
        for x, y in loader:
            x, y = x.to(self.device), y.to(self.device)
            logits = model(x)
            total_loss += criterion(logits, y).item() * x.size(0)
            correct += (logits.argmax(dim=1) == y).sum().item()
            total += x.size(0)

        return {"accuracy": correct / max(total, 1), "loss": total_loss / max(total, 1)}
