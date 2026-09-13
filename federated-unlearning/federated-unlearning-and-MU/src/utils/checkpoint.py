"""
Model checkpointing utilities.

Blueprint principle (§29): "Checkpoint everything important" — M_old,
M_retrain, M_GA, and M_unlearn must all be saveable/loadable in a consistent
way so later phases (unlearning, evaluation) can load exactly the model they
need.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def save_checkpoint(
    model: "torch.nn.Module",
    path: str | Path,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Save model state_dict plus arbitrary metadata (round number, config, etc.)."""
    import torch

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {"model_state_dict": model.state_dict()}
    if extra:
        payload.update(extra)
    torch.save(payload, path)


def load_checkpoint(
    model: "torch.nn.Module",
    path: str | Path,
    map_location: str = "cpu",
) -> Dict[str, Any]:
    """Load a checkpoint's state_dict into `model` in-place. Returns full payload."""
    import torch

    payload = torch.load(Path(path), map_location=map_location)
    model.load_state_dict(payload["model_state_dict"])
    return payload
