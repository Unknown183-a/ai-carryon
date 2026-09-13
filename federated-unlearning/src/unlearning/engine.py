"""Unlearning engine: orchestrates Gradient Ascent + Knowledge Distillation.

STATUS: scaffold — depends on gradient_ascent.py and
knowledge_distillation.py, both currently unimplemented. This file
documents the intended input/output contract (blueprint Section 9) so
the rest of the codebase (experiment runners, evaluation) can be built
against a stable interface ahead of the actual implementation.

Input:  M_old, forget_client_id, forget_client_data, remaining_client_data, config
Output: M_unlearn, metrics, logs, checkpoint
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import torch.nn as nn


@dataclass
class UnlearningResult:
    model: nn.Module
    metrics: Dict[str, Any]


class UnlearningEngine:
    def __init__(self, m_old: nn.Module, config: Dict[str, Any]):
        self.m_old = m_old
        self.config = config

    def run(self, forget_client_id: int, forget_loader, remaining_loader) -> UnlearningResult:
        raise NotImplementedError(
            "UnlearningEngine.run is a scaffold. It will call "
            "GradientAscentUnlearner then KnowledgeDistiller once those "
            "modules are implemented (Phases 4-5, docs/roadmap.md)."
        )
