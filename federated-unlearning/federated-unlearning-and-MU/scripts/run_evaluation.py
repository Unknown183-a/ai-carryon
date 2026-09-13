#!/usr/bin/env python3
"""
Assemble the full comparison table (blueprint §14) from whichever of
M_old / M_retrain / M_GA / M_unlearn checkpoints exist. Models without a
checkpoint yet are simply omitted from the table (never fabricated).

Usage:
    python scripts/run_evaluation.py --partition-metadata experiments/initial_fl/partition_metadata.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets, get_test_loader
from src.data.partition import load_partition_metadata
from src.data.utils import build_client_loaders
from src.evaluation.accuracy import evaluate_accuracy
from src.evaluation.comparison import build_comparison_table, save_comparison_table
from src.models.cnn import build_model
from src.utils.checkpoint import load_checkpoint

CANDIDATE_CHECKPOINTS = {
    "M_old": "experiments/initial_fl/checkpoints/final.pt",
    "M_retrain": "experiments/retraining/checkpoints/final.pt",
    "M_GA": "experiments/gradient_ascent/checkpoints/m_ga.pt",
    "M_unlearn": "experiments/ga_kd/checkpoints/m_unlearn.pt",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition-metadata", required=True)
    parser.add_argument("--forget-client", type=int, default=0)
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--output", default="artifacts/metrics/comparison_table.csv")
    args = parser.parse_args()

    train_dataset, _ = get_mnist_datasets(args.data_dir)
    test_loader = get_test_loader(args.data_dir, batch_size=256)
    partitions = {int(k): v for k, v in load_partition_metadata(args.partition_metadata)["partitions"].items()}
    client_loaders = build_client_loaders(train_dataset, partitions, shuffle=False)
    forget_loader = client_loaders[args.forget_client]

    results = {}
    for name, ckpt_path in CANDIDATE_CHECKPOINTS.items():
        if not Path(ckpt_path).exists():
            print(f"[skip] {name}: no checkpoint at {ckpt_path} yet")
            continue

        model = build_model()
        load_checkpoint(model, ckpt_path)

        overall = evaluate_accuracy(model, test_loader)
        forget = evaluate_accuracy(model, forget_loader)

        results[name] = {
            "overall_accuracy": overall["accuracy"],
            "forget_accuracy": forget["accuracy"],
        }
        print(f"[ok]   {name}: overall_acc={overall['accuracy']:.4f} forget_acc={forget['accuracy']:.4f}")

    if not results:
        print("No checkpoints found yet — run the experiment scripts first.")
        return

    df = build_comparison_table(results)
    save_comparison_table(df, args.output)
    print(f"\nComparison table saved to {args.output}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
