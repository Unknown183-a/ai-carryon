"""Loss functions for the unlearning phase.

STATUS: scaffold only. These are defined so the module boundary and
interface are fixed early, but they are not yet wired into a working
unlearning run — see docs/roadmap.md, Phase 4/5.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def gradient_ascent_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Negative cross-entropy: maximizing this increases loss on the forget set."""
    return -F.cross_entropy(logits, targets)


def kd_loss(student_logits: torch.Tensor, teacher_logits: torch.Tensor, temperature: float = 2.0) -> torch.Tensor:
    """KL(P_teacher || P_student) at temperature T, as in the blueprint's Section 11."""
    student_log_probs = F.log_softmax(student_logits / temperature, dim=1)
    teacher_probs = F.softmax(teacher_logits / temperature, dim=1)
    return F.kl_div(student_log_probs, teacher_probs, reduction="batchmean") * (temperature ** 2)
