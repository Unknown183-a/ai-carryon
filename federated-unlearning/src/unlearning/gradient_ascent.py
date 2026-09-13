"""Gradient Ascent unlearner.

STATUS: interface defined per blueprint Section 10; training loop not
yet implemented/validated against real experiments. Do not treat this
as a working unlearning method until it has been run and evaluated.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

import torch.nn as nn
from torch.utils.data import DataLoader

from .losses import gradient_ascent_loss


class GradientAscentUnlearner:
    def __init__(self, model: nn.Module, config: Dict[str, Any]):
        self.model = copy.deepcopy(model)
        self.config = config

    def unlearn(self, forget_loader: DataLoader) -> nn.Module:
        raise NotImplementedError(
            "GradientAscentUnlearner.unlearn is a scaffold — implement and "
            "validate in Phase 4 (see docs/roadmap.md) before use. Building "
            "this out is intentionally deferred until the FL baseline "
            "(M_old) and full-retraining baseline exist to compare against."
        )
