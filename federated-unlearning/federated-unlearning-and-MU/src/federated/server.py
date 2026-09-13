"""
FL server (blueprint §8).

Responsibilities: hold the global model, distribute it to clients each
round, collect their updates, run FedAvg, and evaluate the aggregated model
on the global test set.
"""
from __future__ import annotations

from typing import Dict, List

from src.federated.client import FederatedClient
from src.federated.fedavg import federated_average


class FederatedServer:
    def __init__(self, global_model, clients: List[FederatedClient], device: str = "cpu"):
        self.global_model = global_model.to(device)
        self.clients = clients
        self.device = device

    def broadcast_and_train_round(self, local_epochs: int, lr: float, momentum: float = 0.9):
        """One communication round: every client trains locally starting from
        the current global model; return their raw update results."""
        results = []
        for client in self.clients:
            result = client.local_train(self.global_model, local_epochs=local_epochs, lr=lr, momentum=momentum)
            results.append(result)
        return results

    def aggregate(self, client_results) -> None:
        """Run FedAvg over client updates and overwrite the global model in place."""
        new_state = federated_average(client_results)
        self.global_model.load_state_dict(new_state)

    def evaluate(self, test_loader) -> Dict[str, float]:
        """Evaluate the current global model on a held-out DataLoader."""
        import torch
        import torch.nn as nn

        self.global_model.eval()
        criterion = nn.CrossEntropyLoss()
        total_loss, correct, total = 0.0, 0, 0

        with torch.no_grad():
            for x, y in test_loader:
                x, y = x.to(self.device), y.to(self.device)
                logits = self.global_model(x)
                loss = criterion(logits, y)
                total_loss += loss.item() * x.size(0)
                correct += (logits.argmax(dim=1) == y).sum().item()
                total += x.size(0)

        return {
            "test_loss": total_loss / max(total, 1),
            "test_accuracy": correct / max(total, 1),
        }
