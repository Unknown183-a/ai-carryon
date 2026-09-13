#!/usr/bin/env python3
"""
Run the full-retraining baseline (blueprint §12): trains M_retrain from
scratch on all clients except the forget client, using the same FL
hyperparameters as the initial experiment for a fair comparison.

Usage:
    python scripts/run_retraining.py --config configs/retraining.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.baselines.full_retraining import run_full_retraining_baseline
from src.data.mnist import get_mnist_datasets, get_test_loader
from src.data.partition import load_partition_metadata
from src.data.utils import build_client_loaders
from src.models.cnn import build_model
from src.utils.config import get, load_config, save_config
from src.utils.reproducibility import set_seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--partition-metadata", default="experiments/initial_fl/partition_metadata.json",
                         help="Reuse the SAME partition as the initial FL run for a fair comparison.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(get(cfg, "project.seed", 42))

    output_dir = Path(get(cfg, "output_dir", "experiments/retraining"))
    output_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, output_dir / "config.yaml")

    device = get(cfg, "device", "cpu")
    data_dir = get(cfg, "dataset.data_dir", "data/raw")
    train_dataset, _ = get_mnist_datasets(data_dir)
    test_loader = get_test_loader(data_dir, batch_size=256)

    meta_path = Path(args.partition_metadata)
    if not meta_path.exists():
        raise FileNotFoundError(f"{meta_path} not found — run the initial FL pipeline first so "
                                 f"retraining uses the identical client partition.")
    partitions = {int(k): v for k, v in load_partition_metadata(meta_path)["partitions"].items()}

    batch_size = get(cfg, "federated.batch_size", 32)
    client_loaders = build_client_loaders(train_dataset, partitions, batch_size=batch_size)

    forget_client = get(cfg, "unlearning.forget_client")
    if forget_client is None:
        raise ValueError("configs/retraining.yaml must set unlearning.forget_client")

    fresh_model = build_model()

    result = run_full_retraining_baseline(
        fresh_model=fresh_model,
        client_loaders=client_loaders,
        forget_client=forget_client,
        test_loader=test_loader,
        rounds=get(cfg, "federated.rounds", 50),
        local_epochs=get(cfg, "federated.local_epochs", 10),
        lr=get(cfg, "federated.local_lr", 0.01),
        momentum=get(cfg, "federated.local_momentum", 0.9),
        output_dir=output_dir,
        device=device,
    )

    with open(output_dir / "summary.json", "w") as f:
        json.dump(
            {"forget_client": forget_client, "final_metrics": result["final_metrics"],
             "total_time_seconds": result["total_time_seconds"]},
            f, indent=2,
        )
    print(f"Done. M_retrain final test accuracy: {result['final_metrics']['test_accuracy']}")


if __name__ == "__main__":
    main()
