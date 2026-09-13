"""
Configuration loading and validation utilities.

Design principle (see blueprint §21, §29): NOTHING about an experiment should
be hard-coded in Python. Every run is fully described by a YAML config file,
optionally overlaid with a base config, so results are reproducible from the
config alone.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import yaml


def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge `override` into `base`, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path, base_path: str | Path | None = "configs/base.yaml") -> Dict[str, Any]:
    """
    Load a YAML config, optionally merged on top of a base config.

    Any key present in `path` overrides the corresponding key in `base_path`.
    This lets every experiment config stay small and only declare what is
    different from the shared defaults.
    """
    path = Path(path)
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    if base_path is not None:
        base_path = Path(base_path)
        if base_path.exists() and base_path.resolve() != path.resolve():
            with open(base_path, "r") as f:
                base_cfg = yaml.safe_load(f) or {}
            cfg = _deep_update(base_cfg, cfg)

    return cfg


def save_config(cfg: Dict[str, Any], path: str | Path) -> None:
    """Persist the (fully resolved) config used for a run, for reproducibility."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def get(cfg: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """Convenience accessor: get(cfg, 'federated.rounds')."""
    node = cfg
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
