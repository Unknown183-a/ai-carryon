"""
Forgetting evaluation (blueprint §13.C): how much does the forget-client's
behavior change after unlearning, relative to M_old and M_retrain?

STATUS: implemented (simple, interpretable metrics). More sophisticated
forgetting metrics (e.g. distributional distance between M_unlearn and
M_retrain predictions) are listed as future extensions (blueprint §28).
"""
from __future__ import annotations

from typing import Dict

from src.evaluation.accuracy import evaluate_accuracy


def forgetting_gap(model, forget_loader, device: str = "cpu") -> Dict[str, float]:
    """Accuracy of `model` on the forget-client's own data. A successful
    forgetting method should show this drop substantially relative to M_old,
    while remaining-client accuracy (see accuracy.py) stays high."""
    return evaluate_accuracy(model, forget_loader, device=device)


def compare_forgetting(m_old, m_unlearn, m_retrain, forget_loader, device: str = "cpu") -> Dict[str, Dict[str, float]]:
    """Side-by-side forget-client accuracy for the three models being compared
    (blueprint §14 comparison table)."""
    return {
        "M_old": forgetting_gap(m_old, forget_loader, device=device),
        "M_unlearn": forgetting_gap(m_unlearn, forget_loader, device=device),
        "M_retrain": forgetting_gap(m_retrain, forget_loader, device=device),
    }
