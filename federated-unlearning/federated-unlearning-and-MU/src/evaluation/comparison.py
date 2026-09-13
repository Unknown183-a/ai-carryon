"""
Model comparison table generator (blueprint §14): assembles the
M_old / M_retrain / M_GA / M_unlearn comparison table from whatever
evaluation results are available. Leaves cells as None (never fabricated
placeholder numbers) until the corresponding experiment has actually run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


COMPARISON_COLUMNS = [
    "model", "overall_accuracy", "remaining_accuracy", "forget_accuracy",
    "mia_attack_accuracy", "time_seconds", "communication_mb",
]


def build_comparison_table(results: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """
    `results` maps model name -> dict of any subset of:
      overall_accuracy, remaining_accuracy, forget_accuracy,
      mia_attack_accuracy, time_seconds, communication_mb

    Missing values are left as None/NaN rather than guessed at, per
    blueprint §14 "Do not populate values until experiments produce them."
    """
    rows = []
    for model_name, metrics in results.items():
        row = {"model": model_name}
        for col in COMPARISON_COLUMNS[1:]:
            row[col] = metrics.get(col)
        rows.append(row)

    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def save_comparison_table(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
