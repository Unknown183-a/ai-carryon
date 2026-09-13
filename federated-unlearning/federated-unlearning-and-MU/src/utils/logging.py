"""
Lightweight experiment logging.

Every experiment run gets:
  - a `training.log` text log (human-readable, timestamped)
  - a `metrics.csv` structured log (one row per logged event, easy to plot)

Kept dependency-free (stdlib only) so it works even before heavier
dependencies (torch, pandas) are installed.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_logger(name: str, log_file: str | Path) -> logging.Logger:
    """Create/return a logger that writes to both console and `log_file`."""
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # avoid duplicate handlers if called twice

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


class MetricsLogger:
    """Append-only CSV metrics logger, e.g. one row per communication round."""

    def __init__(self, csv_path: str | Path, fieldnames: Optional[List[str]] = None):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.fieldnames = fieldnames
        self._initialized = self.csv_path.exists()

    def log(self, row: Dict[str, Any]) -> None:
        if self.fieldnames is None:
            self.fieldnames = list(row.keys())

        write_header = not self._initialized
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        self._initialized = True
