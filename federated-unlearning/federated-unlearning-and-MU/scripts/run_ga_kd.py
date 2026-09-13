#!/usr/bin/env python3
"""
Run the full proposed unlearning pipeline: Gradient Ascent + Knowledge
Distillation (M_old -> M_unlearn), blueprint §9-§11.

Usage:
    python scripts/run_ga_kd.py --config configs/ga_kd.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets
from src.data.partition import load_partition_metadata
from src.data.utils import build_client_loaders, exclude_client
from src.models.cnn import build_model
from src.unlearning.engine import run_unlearning
from src.utils.checkpoint import load_checkpoint
from src.utils.config import get, load_config, save_config
from src.utils.reproducibility import set_seed
from torch.utils.data import ConcatDataset, DataLoader, Subset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--partition-metadata", default="experiments/initial_fl/partition_metadata.json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(get(cfg, "project.seed", 42))

    output_dir = Path(get(cfg, "output_dir", "experiments/ga_kd"))
    output_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, output_dir / "config.yaml")

    device = get(cfg, "device", "cpu")
    data_dir = get(cfg, "dataset.data_dir", "data/raw")
    train_dataset, _ = get_mnist_datasets(data_dir)

    partitions = {int(k): v for k, v in load_partition_metadata(args.partition_metadata)["partitions"].items()}
    batch_size = get(cfg, "federated.batch_size", 32)
    client_loaders = build_client_loaders(train_dataset, partitions, batch_size=batch_size)

    forget_client = get(cfg, "unlearning.forget_client")
    forget_loader = client_loaders[forget_client]

    remaining_partitions = exclude_client(partitions, forget_client)
    remaining_indices = [i for idx in remaining_partitions.values() for i in idx]
    remaining_loader = DataLoader(Subset(train_dataset, remaining_indices), batch_size=batch_size, shuffle=True)

    m_old = build_model()
    ckpt_path = get(cfg, "input_checkpoint")
    if not ckpt_path or not Path(ckpt_path).exists():
        raise FileNotFoundError(f"input_checkpoint {ckpt_path!r} not found — "
                                 f"run scripts/run_initial_fl.py first to produce M_old.")
    load_checkpoint(m_old, ckpt_path)

    result = run_unlearning(
        m_old=m_old,
        forget_loader=forget_loader,
        remaining_loader=remaining_loader,
        config=cfg,
        output_dir=output_dir,
        device=device,
    )

    with open(output_dir / "summary.json", "w") as f:
        json.dump(result["summary"], f, indent=2, default=str)

    print("Done. M_unlearn checkpoint saved to "
          f"{output_dir / 'checkpoints' / 'm_unlearn.pt'}")


if __name__ == "__main__":
    main()
