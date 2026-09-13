# Phase 01 — Data Pipeline

**Status:** Complete
**Depends on:** Phase 00

## Goal

Load MNIST and split it across simulated clients, both IID and Non-IID.

## Tasks

- [x] `src/data/mnist.py` — download/load/normalize MNIST
- [x] `src/data/partition.py` — IID partition + Non-IID Dirichlet partition
- [x] `src/data/utils.py` — save partition metadata (label counts per client) for reproducibility
- [x] Unit tests (`tests/test_data.py`)

## Definition of done

`partition_dataset()` covers 100% of samples for both strategies; metadata JSON is written per experiment.

## Handoff notes

Non-IID uses a Dirichlet(alpha) split per class — lower alpha means more label skew. alpha is config-driven, not hard-coded.
