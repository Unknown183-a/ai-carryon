#!/usr/bin/env python3
"""
Download MNIST and materialize the client partition used by an experiment.

Usage:
    python scripts/prepare_data.py --config configs/initial_fl.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets
from src.data.partition import partition_dataset, save_partition_metadata
from src.utils.config import get, load_config
from src.utils.reproducibility import set_seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(get(cfg, "project.seed", 42))

    data_dir = get(cfg, "dataset.data_dir", "data/raw")
    print(f"Downloading/loading MNIST into {data_dir} ...")
    train_dataset, test_dataset = get_mnist_datasets(data_dir)
    print(f"Train samples: {len(train_dataset)}, Test samples: {len(test_dataset)}")

    num_clients = get(cfg, "clients.num_clients", 5)
    distribution = get(cfg, "dataset.distribution", "iid")
    seed = get(cfg, "project.seed", 42)

    print(f"Partitioning into {num_clients} clients ({distribution}) ...")
    partitions = partition_dataset(
        train_dataset,
        num_clients=num_clients,
        distribution=distribution,
        seed=seed,
        shards_per_client=get(cfg, "dataset.non_iid_shards_per_client", 2),
    )

    output_dir = Path(get(cfg, "output_dir", "experiments/initial_fl"))
    meta_path = output_dir / "partition_metadata.json"
    save_partition_metadata(partitions, meta_path, distribution=distribution, seed=seed)

    for cid, idx in partitions.items():
        print(f"  client {cid}: {len(idx)} samples")
    print(f"Partition metadata saved to {meta_path}")


if __name__ == "__main__":
    main()
