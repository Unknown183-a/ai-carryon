"""Load experiment configuration from YAML.

No experiment parameters (client count, rounds, epochs, lr, forget
client, etc.) should ever be hard-coded in the source — everything
comes through this config loader instead.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import yaml


class Config(dict):
    """Dict subclass that also supports attribute access, e.g. cfg.data.batch_size."""

    def __getattr__(self, name: str) -> Any:
        try:
            value = self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return Config(value) if isinstance(value, dict) else value

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def load_config(path: str | Path) -> Config:
    path = Path(path)
    with path.open("r") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)
    return Config(copy.deepcopy(raw))


def save_config(cfg: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump(dict(cfg), f, sort_keys=False)
