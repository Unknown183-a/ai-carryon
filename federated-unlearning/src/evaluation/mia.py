"""Membership Inference Attack (MIA) scaffold.

STATUS: not implemented. Blueprint Section 13/RQ6 calls for evaluating
whether forgotten samples remain distinguishable as training members
after unlearning. This requires a trained M_unlearn and a chosen
attack methodology (e.g. shadow-model or confidence-threshold MIA),
neither of which exist yet.
"""
from __future__ import annotations

from typing import Any, Dict

import torch.nn as nn


def run_mia(model: nn.Module, member_loader, non_member_loader) -> Dict[str, Any]:
    raise NotImplementedError("MIA scaffold — implement in Phase 6 (docs/roadmap.md).")
