#!/usr/bin/env python3
"""
Run the initial FL pipeline-validation experiment (blueprint §6):
MNIST, 5 clients, 50 communication rounds, 10 local epochs/round, FedAvg.

Usage:
    python scripts/prepare_data.py --config configs/initial_fl.yaml
    python scripts/run_initial_fl.py --config configs/initial_fl.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets, get_test_loader
from src.data.partition import load_partition_metadata
from src.data.utils import build_client_loaders
from src.federated.client import FederatedClient
from src.federated.round_manager import run_federated_training
from src.federated.server import FederatedServer
from src.models.cnn import build_model, count_parameters
from src.utils.config import get, load_config, save_config
from src.utils.reproducibility import set_seed, snapshot_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    seed = get(cfg, "project.seed", 42)
    set_seed(seed)

    output_dir = Path(get(cfg, "output_dir", "experiments/initial_fl"))
    output_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, output_dir / "config.yaml")
    with open(output_dir / "environment.json", "w") as f:
        json.dump(snapshot_environment(), f, indent=2)

    device = get(cfg, "device", "cpu")
    data_dir = get(cfg, "dataset.data_dir", "data/raw")
    train_dataset, test_dataset = get_mnist_datasets(data_dir)
    test_loader = get_test_loader(data_dir, batch_size=256)

    meta_path = output_dir / "partition_metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"{meta_path} not found — run scripts/prepare_data.py with the same "
            f"config first to generate the client partition."
        )
    partitions = {int(k): v for k, v in load_partition_metadata(meta_path)["partitions"].items()}

    batch_size = get(cfg, "federated.batch_size", 32)
    client_loaders = build_client_loaders(train_dataset, partitions, batch_size=batch_size)

    clients = [FederatedClient(client_id=cid, data_loader=loader, device=device)
               for cid, loader in client_loaders.items()]

    model = build_model()
    print(f"Model parameter count: {count_parameters(model):,}")

    server = FederatedServer(model, clients, device=device)

    result = run_federated_training(
        server=server,
        test_loader=test_loader,
        rounds=get(cfg, "federated.rounds", 50),
        local_epochs=get(cfg, "federated.local_epochs", 10),
        lr=get(cfg, "federated.local_lr", 0.01),
        momentum=get(cfg, "federated.local_momentum", 0.9),
        output_dir=output_dir,
        run_name="initial_fl_pipeline_validation",
    )

    with open(output_dir / "summary.json", "w") as f:
        json.dump(
            {"final_metrics": result["final_metrics"], "total_time_seconds": result["total_time_seconds"]},
            f, indent=2,
        )

    print(f"Done. Final test accuracy: {result['final_metrics']['test_accuracy']}")
    print(f"Full results in: {output_dir}")


if __name__ == "__main__":
    main()
