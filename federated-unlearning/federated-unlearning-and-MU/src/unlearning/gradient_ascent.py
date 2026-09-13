"""
Gradient Ascent unlearning (blueprint §10).

Normal training step:      W <- W - eta * grad(L)
Forgetting step (ascent):   W <- W + eta * grad(L_forget)

Implemented as an SGD step on the *negated* forget loss, which is
mathematically equivalent to ascending L_forget directly, and lets us reuse
torch's built-in optimizers instead of hand-rolling parameter updates.

STATUS: implemented, matches the blueprint's suggested interface. Not yet
run as part of a real experiment — no forgetting results exist until
scripts/run_gradient_ascent.py is actually executed against a trained M_old.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict


@dataclass
class GradientAscentResult:
    state_dict: Dict
    final_forget_loss: float
    epochs_run: int
    train_time_seconds: float


class GradientAscentUnlearner:
    """
    Suggested interface (blueprint §10):

        class GradientAscentUnlearner:
            def __init__(self, model, config): ...
            def unlearn(self, forget_loader): ...
    """

    def __init__(self, model, config: dict):
        """
        config keys (all required, no hard-coded defaults per blueprint §29):
          - learning_rate: float
          - epochs: int
          - momentum: float (optional, default 0.9)
          - max_forget_loss: float (optional) — safety cap; if L_forget
            exceeds this, ascent stops early to avoid destroying the model
            entirely (a purely divergent loss is not useful "forgetting").
        """
        self.model = model
        self.config = config

    def unlearn(self, forget_loader, device: str = "cpu") -> GradientAscentResult:
        import time

        import torch
        import torch.optim as optim

        from src.unlearning.losses import forget_loss

        model = copy.deepcopy(self.model).to(device)
        model.train()

        lr = self.config["learning_rate"]
        epochs = self.config["epochs"]
        momentum = self.config.get("momentum", 0.9)
        max_forget_loss = self.config.get("max_forget_loss", None)

        optimizer = optim.SGD(model.parameters(), lr=lr, momentum=momentum)

        start = time.time()
        last_loss = None
        epochs_run = 0

        for epoch in range(epochs):
            epochs_run = epoch + 1
            for x, y in forget_loader:
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad()
                logits = model(x)
                loss = forget_loss(logits, y)

                # Ascent: minimize the *negative* loss == maximize the loss.
                (-loss).backward()
                optimizer.step()

                last_loss = loss.item()

            if max_forget_loss is not None and last_loss is not None and last_loss >= max_forget_loss:
                break

        elapsed = time.time() - start
        return GradientAscentResult(
            state_dict=copy.deepcopy(model.state_dict()),
            final_forget_loss=last_loss if last_loss is not None else float("nan"),
            epochs_run=epochs_run,
            train_time_seconds=elapsed,
        )
