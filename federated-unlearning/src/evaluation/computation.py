"""Computation-cost measurement: wall-clock training/unlearning time, epoch/round counts."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, Iterator


@contextmanager
def timer() -> Iterator[Dict[str, float]]:
    """Usage: with timer() as t: ... ; t['seconds'] holds the elapsed time afterward."""
    result: Dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - start
