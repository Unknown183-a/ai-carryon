#!/usr/bin/env python3
"""
Run the baseline MIA evaluation (blueprint §13.D, scaffold — see
src/evaluation/mia.py docstring for caveats).

Usage:
    python scripts/run_mia.py --model-checkpoint experiments/ga_kd/checkpoints/m_unlearn.pt \
        --forget-client 0 --partition-metadata experiments/initial_fl/partition_metadata.json
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
from src.evaluation.mia import simple_confidence_threshold_mia
from src.models.cnn import build_model
from src.utils.checkpoint import load_checkpoint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-checkpoint", required=True)
    parser.add_argument("--forget-client", type=int, required=True)
    parser.add_argument("--partition-metadata", required=True)
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--output", default=None, help="Optional path to write JSON result.")
    args = parser.parse_args()

    model = build_model()
    load_checkpoint(model, args.model_checkpoint)

    train_dataset, _ = get_mnist_datasets(args.data_dir)
    partitions = {int(k): v for k, v in load_partition_metadata(args.partition_metadata)["partitions"].items()}
    client_loaders = build_client_loaders(train_dataset, partitions, shuffle=False)

    member_loader = client_loaders[args.forget_client]
    non_member_loader = get_test_loader(args.data_dir, batch_size=256)

    result = simple_confidence_threshold_mia(model, member_loader, non_member_loader)
    print(json.dumps(result, indent=2))

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
