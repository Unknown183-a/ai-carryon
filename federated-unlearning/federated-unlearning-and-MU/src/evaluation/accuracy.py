"""
Accuracy evaluation (blueprint §13.A, §13.B): overall test-set accuracy and
per-client accuracy, used both for "remaining-client performance" and
"forget-client performance" (which is really the same function applied to
different data slices).
"""
from __future__ import annotations

from typing import Dict


def evaluate_accuracy(model, data_loader, device: str = "cpu") -> Dict[str, float]:
    """Standard classification accuracy + loss on any DataLoader."""
    import torch
    import torch.nn as nn

    model = model.to(device)
    model.eval()
    criterion = nn.CrossEntropyLoss()
    total_loss, correct, total = 0.0, 0, 0

    with torch.no_grad():
        for x, y in data_loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = criterion(logits, y)
            total_loss += loss.item() * x.size(0)
            correct += (logits.argmax(dim=1) == y).sum().item()
            total += x.size(0)

    return {
        "loss": total_loss / max(total, 1),
        "accuracy": correct / max(total, 1),
        "num_samples": total,
    }


def evaluate_per_client(model, client_loaders: Dict[int, "DataLoader"], device: str = "cpu") -> Dict[int, Dict[str, float]]:
    """Evaluate the same model on each client's own held-out data separately."""
    return {cid: evaluate_accuracy(model, loader, device=device) for cid, loader in client_loaders.items()}
