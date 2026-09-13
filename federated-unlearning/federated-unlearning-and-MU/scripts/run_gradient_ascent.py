#!/usr/bin/env python3
"""
Run Gradient-Ascent-only unlearning (M_old -> M_GA), blueprint §10.

Usage:
    python scripts/run_gradient_ascent.py --config configs/gradient_ascent.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets
from src.data.partition import load_partition_metadata
from src.data.utils import build_client_loaders
from src.models.cnn import build_model
from src.unlearning.gradient_ascent import GradientAscentUnlearner
from src.utils.checkpoint import load_checkpoint, save_checkpoint
from src.utils.config import get, load_config, save_config
from src.utils.reproducibility import set_seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--partition-metadata", default="experiments/initial_fl/partition_metadata.json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(get(cfg, "project.seed", 42))

    output_dir = Path(get(cfg, "output_dir", "experiments/gradient_ascent"))
    output_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, output_dir / "config.yaml")

    device = get(cfg, "device", "cpu")
    data_dir = get(cfg, "dataset.data_dir", "data/raw")
    train_dataset, _ = get_mnist_datasets(data_dir)

    partitions = {int(k): v for k, v in load_partition_metadata(args.partition_metadata)["partitions"].items()}
    client_loaders = build_client_loaders(train_dataset, partitions, batch_size=get(cfg, "federated.batch_size", 32))

    forget_client = get(cfg, "unlearning.forget_client")
    forget_loader = client_loaders[forget_client]

    m_old = build_model()
    ckpt_path = get(cfg, "input_checkpoint")
    if not ckpt_path or not Path(ckpt_path).exists():
        raise FileNotFoundError(f"input_checkpoint {ckpt_path!r} not found — "
                                 f"run scripts/run_initial_fl.py first to produce M_old.")
    load_checkpoint(m_old, ckpt_path)

    unlearner = GradientAscentUnlearner(m_old, get(cfg, "unlearning.gradient_ascent"))
    result = unlearner.unlearn(forget_loader, device=device)

    m_ga = build_model()
    m_ga.load_state_dict(result.state_dict)
    save_checkpoint(m_ga, output_dir / "checkpoints" / "m_ga.pt", extra={"result": vars(result)})

    with open(output_dir / "summary.json", "w") as f:
        json.dump(vars(result), f, indent=2, default=str)

    print(f"Done. Final forget loss: {result.final_forget_loss:.4f} (epochs_run={result.epochs_run})")
    print(f"M_GA checkpoint saved to {output_dir / 'checkpoints' / 'm_ga.pt'}")


if __name__ == "__main__":
    main()
