"""
Membership Inference Attack scaffold (blueprint §13.D, §15 RQ6).

Goal: evaluate whether the forget-client's samples remain distinguishable as
"members" of the training set after unlearning — i.e. does M_unlearn's
behavior on forgotten data still look like training-set behavior (high
confidence, low loss) rather than unseen-data behavior?

STATUS: SCAFFOLD ONLY. A simple loss/confidence-threshold attack is
implemented as a reasonable starting point; this is explicitly called out in
the blueprint as needing a Phase-6 implementation and is one of the
"Future Extensions" (§28) to make "more sophisticated". Do not treat its
output as a validated MIA result until it has been run and reviewed.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


def _per_sample_confidence_and_loss(model, data_loader, device: str = "cpu"):
    import torch
    import torch.nn.functional as F

    model = model.to(device)
    model.eval()
    confidences, losses = [], []

    with torch.no_grad():
        for x, y in data_loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            probs = F.softmax(logits, dim=1)
            conf = probs.gather(1, y.unsqueeze(1)).squeeze(1)
            loss = F.cross_entropy(logits, y, reduction="none")
            confidences.append(conf.cpu().numpy())
            losses.append(loss.cpu().numpy())

    return np.concatenate(confidences), np.concatenate(losses)


def simple_confidence_threshold_mia(
    model,
    member_loader,
    non_member_loader,
    device: str = "cpu",
) -> Dict[str, float]:
    """
    Baseline MIA: fit the single confidence threshold that best separates
    `member_loader` (e.g. the forget client's training data) from
    `non_member_loader` (e.g. the global test set, never trained on), then
    report the resulting attack accuracy.

    An attack accuracy near 0.5 suggests the two are indistinguishable
    (good forgetting / good privacy); an accuracy well above 0.5 suggests
    membership is still detectable.

    NOTE: this is a simple baseline attack, not a comprehensive MIA
    evaluation. Treat results as indicative only (see module docstring).
    """
    member_conf, _ = _per_sample_confidence_and_loss(model, member_loader, device=device)
    non_member_conf, _ = _per_sample_confidence_and_loss(model, non_member_loader, device=device)

    labels = np.concatenate([np.ones_like(member_conf), np.zeros_like(non_member_conf)])
    scores = np.concatenate([member_conf, non_member_conf])

    thresholds = np.unique(scores)
    best_acc = 0.0
    best_threshold = 0.5
    for t in thresholds:
        preds = (scores >= t).astype(int)
        acc = (preds == labels).mean()
        if acc > best_acc:
            best_acc = acc
            best_threshold = float(t)

    return {
        "attack_accuracy": float(best_acc),
        "best_threshold": best_threshold,
        "num_member_samples": int(len(member_conf)),
        "num_non_member_samples": int(len(non_member_conf)),
    }
