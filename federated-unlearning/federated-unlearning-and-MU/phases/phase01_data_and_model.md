# Phase 1 — Data Pipeline & Model

**Status: COMPLETE**

## Goals
- Load MNIST and apply standard normalization.
- Partition the training set across N simulated clients (IID and Non-IID).
- Define a small CNN suitable for MNIST classification.

## Deliverables
- `src/data/mnist.py`, `src/data/partition.py`, `src/data/utils.py`
- `src/models/cnn.py`
- `scripts/prepare_data.py`
- `tests/test_data.py`, `tests/test_model.py`

## Verification
`pytest tests/test_data.py tests/test_model.py -v` — all passing.
