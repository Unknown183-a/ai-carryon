"""Run the initial FL pipeline-validation experiment (blueprint Section 6).

Usage:
    python experiments/run_initial_fl.py --config configs/initial_fl.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mnist import get_mnist_datasets
from src.data.partition import partition_dataset
from src.data.utils import save_partition_metadata
from src.federated.client import FederatedClient
from src.federated.server import FederatedServer
from src.models.cnn import build_model
from src.utils.config import load_config, save_config
from src.utils.seed import set_seed


def main(config_path: str) -> None:
    cfg = load_config(config_path)
    set_seed(cfg.seed)

    artifacts_dir = Path(cfg.output.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, artifacts_dir / "config.yaml")

    train_set, test_set = get_mnist_datasets(cfg.data.data_dir)
    client_datasets = partition_dataset(
        train_set,
        num_clients=cfg.data.num_clients,
        strategy=cfg.data.partition,
        alpha=cfg.data.get("non_iid_alpha", 0.5),
        seed=cfg.seed,
    )
    save_partition_metadata(client_datasets, artifacts_dir / "partition_metadata.json")

    clients = {
        cid: FederatedClient(cid, ds, batch_size=cfg.data.batch_size, device=cfg.device)
        for cid, ds in client_datasets.items()
    }
    test_client = FederatedClient(-1, test_set, batch_size=cfg.data.batch_size, device=cfg.device)

    global_model = build_model(cfg.model.name, num_classes=cfg.model.num_classes)

    server = FederatedServer(
        global_model=global_model,
        clients=clients,
        artifacts_dir=artifacts_dir,
        save_every_n_rounds=cfg.output.save_every_n_rounds,
    )
    server.run(
        num_rounds=cfg.federated.num_rounds,
        local_epochs=cfg.federated.local_epochs,
        local_lr=cfg.federated.local_lr,
        test_client=test_client,
    )
    print(f"Done. Artifacts written to {artifacts_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/initial_fl.yaml")
    args = parser.parse_args()
    main(args.config)
