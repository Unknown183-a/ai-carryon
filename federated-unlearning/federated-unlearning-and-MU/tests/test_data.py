from src.data.partition import partition_iid, partition_non_iid, partition_dataset
import numpy as np


def test_partition_iid_covers_all_indices_no_overlap():
    labels = np.random.randint(0, 10, size=100)
    partitions = partition_iid(labels, num_clients=5, seed=1)

    assert len(partitions) == 5
    all_indices = sorted(i for idx in partitions.values() for i in idx)
    assert all_indices == list(range(100))


def test_partition_non_iid_covers_all_indices_no_overlap():
    labels = np.random.randint(0, 10, size=100)
    partitions = partition_non_iid(labels, num_clients=5, shards_per_client=2, seed=1)

    assert len(partitions) == 5
    all_indices = sorted(i for idx in partitions.values() for i in idx)
    assert all_indices == list(range(100))


def test_partition_dataset_respects_num_clients(tiny_dataset):
    partitions = partition_dataset(tiny_dataset, num_clients=5, distribution="iid", seed=1)
    assert len(partitions) == 5


def test_partition_dataset_invalid_distribution_raises(tiny_dataset):
    import pytest

    with pytest.raises(ValueError):
        partition_dataset(tiny_dataset, num_clients=5, distribution="bogus")
