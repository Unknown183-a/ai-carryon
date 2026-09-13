# Phase 02 — Model + FedAvg

**Status:** Complete
**Depends on:** Phase 01

## Goal

Small CNN for MNIST, a federated client that trains/evaluates locally, and FedAvg aggregation.

## Tasks

- [x] `src/models/cnn.py` — SimpleCNN + `build_model()` factory
- [x] `src/federated/client.py` — local train/evaluate, returns a `ClientUpdate`
- [x] `src/federated/fedavg.py` — sample-weighted parameter averaging
- [x] Unit tests (`tests/test_model.py`, `tests/test_fedavg.py`)

## Definition of done

FedAvg output matches a manually-computed weighted average in the unit test; CNN forward pass produces correct output shape.

## Handoff notes

Kept intentionally small (2 conv layers) since this phase is about pipeline correctness, not accuracy.
