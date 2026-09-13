"""
Forget-client selection utilities (blueprint §9 "Input: Forget Client ID").

Deliberately tiny: selection logic is trivial (an index/ID), but is kept as
its own module so the *decision* of which client to forget is explicit,
config-driven, logged, and reproducible rather than implicit in a script.
"""
from __future__ import annotations

from typing import Dict, List


def select_forget_client(config: dict) -> int:
    """Read the forget-client ID from config (never hard-code it, blueprint §29)."""
    forget_client = config.get("unlearning", {}).get("forget_client")
    if forget_client is None:
        raise ValueError("config.unlearning.forget_client must be set to select a client to forget.")
    return int(forget_client)


def split_forget_and_remaining(
    partitions: Dict[int, List[int]], forget_client: int
) -> tuple[List[int], Dict[int, List[int]]]:
    """Return (forget_client_indices, {remaining client_id: indices})."""
    if forget_client not in partitions:
        raise KeyError(f"forget_client={forget_client} not found in partitions "
                        f"(available clients: {sorted(partitions.keys())})")
    forget_indices = partitions[forget_client]
    remaining = {cid: idx for cid, idx in partitions.items() if cid != forget_client}
    return forget_indices, remaining
