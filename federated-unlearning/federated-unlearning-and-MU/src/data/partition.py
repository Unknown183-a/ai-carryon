"""
Client partitioning: split a dataset across simulated FL clients.

Blueprint §3 / §15: supports both IID and Non-IID partitioning, and the
number of clients must come from config, never be hard-coded (§29).

Partition metadata (which sample indices went to which client, and under
which distribution/seed) is saved alongside the partition so that:
  1. The forget-client's exact data can be reconstructed later for
     unlearning (blueprint §9 "Input: Forget Client Data").
  2. The full-retraining baseline can reproduce "all clients except Ck".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np


def partition_iid(labels: np.ndarray, num_clients: int, seed: int = 42) -> Dict[int, List[int]]:
    """Randomly (uniformly) split indices across clients, ignoring labels."""
    rng = np.random.default_rng(seed)
    indices = np.arange(len(labels))
    rng.shuffle(indices)
    shards = np.array_split(indices, num_clients)
    return {client_id: shard.tolist() for client_id, shard in enumerate(shards)}


def partition_non_iid(
    labels: np.ndarray,
    num_clients: int,
    shards_per_client: int = 2,
    seed: int = 42,
) -> Dict[int, List[int]]:
    """
    Classic "sort-by-label then shard" non-IID partition (McMahan et al. 2017
    style): sort all samples by label, split into `num_clients *
    shards_per_client` contiguous shards, and assign `shards_per_client`
    random shards to each client. Lower `shards_per_client` => more skewed
    (fewer distinct labels per client).
    """
    rng = np.random.default_rng(seed)
    num_shards = num_clients * shards_per_client

    sorted_indices = np.argsort(labels)
    shard_splits = np.array_split(sorted_indices, num_shards)

    shard_order = rng.permutation(num_shards)
    client_shards: Dict[int, List[int]] = {c: [] for c in range(num_clients)}
    for i, shard_id in enumerate(shard_order):
        client_id = i % num_clients
        client_shards[client_id].extend(shard_splits[shard_id].tolist())

    return client_shards


def partition_dataset(
    dataset,
    num_clients: int,
    distribution: str = "iid",
    seed: int = 42,
    shards_per_client: int = 2,
) -> Dict[int, List[int]]:
    """
    Partition `dataset` (a torchvision-style dataset with `.targets`) into
    `num_clients` index lists according to `distribution` ("iid" or "non_iid").
    """
    labels = np.array(dataset.targets)

    if distribution == "iid":
        return partition_iid(labels, num_clients, seed=seed)
    elif distribution == "non_iid":
        return partition_non_iid(labels, num_clients, shards_per_client=shards_per_client, seed=seed)
    else:
        raise ValueError(f"Unknown distribution: {distribution!r} (expected 'iid' or 'non_iid')")


def save_partition_metadata(
    partitions: Dict[int, List[int]],
    path: str | Path,
    distribution: str,
    seed: int,
) -> None:
    """Persist which sample indices went to which client (for reproducibility
    and so the unlearning phase can reconstruct the forget-client's exact data)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "distribution": distribution,
        "seed": seed,
        "num_clients": len(partitions),
        "client_sizes": {cid: len(idx) for cid, idx in partitions.items()},
        "partitions": partitions,
    }
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)


def load_partition_metadata(path: str | Path) -> Dict:
    with open(Path(path), "r") as f:
        return json.load(f)
