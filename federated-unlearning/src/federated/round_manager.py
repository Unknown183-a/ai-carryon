"""Tracks per-round metrics across a federated training run."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


class RoundManager:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def record(self, round_num: int, **metrics: Any) -> None:
        self.history.append({"round": round_num, **metrics})

    def save_csv(self, path: str | Path) -> None:
        if not self.history:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(self.history[0].keys())
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.history)
