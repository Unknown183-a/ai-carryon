"""
Loss terms for the unlearning engine (blueprint §9–§11).

Kept separate from gradient_ascent.py / knowledge_distillation.py so the
combined objective

    L_total = lambda_forget * L_forget + lambda_KD * L_KD

can be composed and swapped without touching the training loops.

STATUS: implemented per the blueprint's specified formulas, but not yet
validated against any experiment (no results have been generated with these
losses — see docs/methodology.md).
"""
from __future__ import annotations


def forget_loss(logits, targets):
    """L_forget: standard cross-entropy on the forget client's data.
    Gradient ASCENT on this loss (see gradient_ascent.py) increases it,
    which is what drives the model to forget the target client."""
    import torch.nn.functional as F

    return F.cross_entropy(logits, targets)


def kd_loss(student_logits, teacher_logits, temperature: float = 4.0):
    """
    L_KD = KL(P_teacher || P_student), computed at temperature T, as in
    Hinton et al. distillation. `teacher_logits` should come from M_old
    with gradients disabled.
    """
    import torch.nn.functional as F

    student_log_probs = F.log_softmax(student_logits / temperature, dim=1)
    teacher_probs = F.softmax(teacher_logits / temperature, dim=1)
    # batchmean + T^2 scaling per Hinton et al. (2015) so gradient magnitude
    # is comparable across temperature choices.
    return F.kl_div(student_log_probs, teacher_probs, reduction="batchmean") * (temperature ** 2)


def combined_unlearning_loss(
    forget_logits,
    forget_targets,
    student_logits,
    teacher_logits,
    lambda_forget: float = 1.0,
    lambda_kd: float = 1.0,
    temperature: float = 4.0,
):
    """
    L_total = lambda_forget * L_forget + lambda_kd * L_KD

    NOTE: this combines a forget term (to be ASCENDED, i.e. subtracted from
    the model's parameters via a negative-loss step) with a KD term (to be
    DESCENDED). The unlearning engine (engine.py) is responsible for applying
    ascent/descent directions correctly per blueprint §10; this function only
    computes the two scalar loss values.
    """
    l_forget = forget_loss(forget_logits, forget_targets)
    l_kd = kd_loss(student_logits, teacher_logits, temperature=temperature)
    l_total = lambda_forget * l_forget + lambda_kd * l_kd
    return l_total, {"forget_loss": l_forget.item(), "kd_loss": l_kd.item()}
