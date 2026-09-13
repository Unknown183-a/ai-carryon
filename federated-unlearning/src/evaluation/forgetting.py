"""Forget-client behavior-change metric.

STATUS: scaffold. Depends on having both M_old and M_unlearn, so it
can't be meaningfully implemented until the unlearning engine
(Phase 4-5) exists.
"""
from __future__ import annotations

from typing import Any, Dict

import torch.nn as nn


def forgetting_score(m_old: nn.Module, m_unlearn: nn.Module, forget_loader) -> Dict[str, Any]:
    raise NotImplementedError("Requires a trained M_unlearn — see docs/roadmap.md Phase 6.")
