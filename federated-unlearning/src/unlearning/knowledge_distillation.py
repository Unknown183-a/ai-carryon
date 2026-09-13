"""Knowledge Distillation module (teacher = M_old, student = model being unlearned).

STATUS: interface defined per blueprint Section 11; not yet implemented.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

import torch.nn as nn
from torch.utils.data import DataLoader


class KnowledgeDistiller:
    def __init__(self, teacher: nn.Module, student: nn.Module, config: Dict[str, Any]):
        self.teacher = teacher
        self.student = copy.deepcopy(student)
        self.config = config

    def distill(self, remaining_loader: DataLoader) -> nn.Module:
        raise NotImplementedError(
            "KnowledgeDistiller.distill is a scaffold — implement in Phase 5 "
            "(see docs/roadmap.md). Uses kd_loss from losses.py with the "
            "temperature configured in configs/unlearning.yaml."
        )
