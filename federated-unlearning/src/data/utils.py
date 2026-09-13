"""Partition metadata helpers (label counts per client, saved for reproducibility)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from torch.utils.data import Subset


def partition_summary(client_datasets: Dict[int, Subset]) -> Dict[int, Dict[str, int]]:
    summary: Dict[int, Dict[str, int]] = {}
    for cid, subset in client_datasets.items():
        labels = [subset.dataset[i][1] for i in subset.indices]
        counts: Dict[str, int] = {}
        for label in labels:
            key = str(int(label))
            counts[key] = counts.get(key, 0) + 1
        summary[cid] = {"num_samples": len(labels), "label_counts": counts}
    return summary


def save_partition_metadata(client_datasets: Dict[int, Subset], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(partition_summary(client_datasets), f, indent=2)
