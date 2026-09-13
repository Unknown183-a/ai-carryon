"""Generates the model-comparison table (blueprint Section 14).

Populates only the metrics actually passed in — never fabricates
values for models that haven't been evaluated yet.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


def build_comparison_table(rows: List[Dict[str, Any]], path: str | Path) -> None:
    """rows: list of dicts like {'model': 'M_old', 'overall_accuracy': 0.97, ...}.

    Any metric key missing for a given row is left blank in the CSV
    rather than filled in with a placeholder number.
    """
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
