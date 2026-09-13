"""
Computation-cost measurement (blueprint §13.E).

Rather than re-deriving cost analytically, this module reads the timing and
round/epoch counts that round_manager.py / engine.py already log to each
run's metrics.csv, and turns them into the comparison numbers blueprint §14
wants (e.g. "unlearning took X seconds vs Y seconds for full retraining").
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def summarize_computation_cost(metrics_csv_path: str | Path) -> Dict[str, float]:
    """Summarize total wall-clock time and round/epoch counts from a run's metrics.csv."""
    path = Path(metrics_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No metrics.csv found at {path} — has this experiment been run yet?")

    df = pd.read_csv(path)
    summary: Dict[str, float] = {}

    if "round_time_seconds" in df.columns:
        summary["total_time_seconds"] = float(df["round_time_seconds"].sum())
        summary["num_rounds"] = int(len(df))
        summary["avg_round_time_seconds"] = float(df["round_time_seconds"].mean())
    elif "total_time_seconds" in df.columns:
        summary["total_time_seconds"] = float(df["total_time_seconds"].iloc[-1])

    return summary


def compare_computation_cost(*, unlearn_metrics_csv: str | Path, retrain_metrics_csv: str | Path) -> Dict:
    """Compute the (retrain_time / unlearn_time) speedup factor between two runs."""
    unlearn = summarize_computation_cost(unlearn_metrics_csv)
    retrain = summarize_computation_cost(retrain_metrics_csv)

    speedup = None
    if unlearn.get("total_time_seconds", 0) > 0:
        speedup = retrain.get("total_time_seconds", 0) / unlearn["total_time_seconds"]

    return {"unlearning": unlearn, "retraining": retrain, "speedup_factor": speedup}
