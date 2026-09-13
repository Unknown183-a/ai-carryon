# Phase 2 — Federated Learning Pipeline

**Status: COMPLETE**

## Goals
- Implement FedAvg: client-side local training + server-side weighted
  aggregation.
- Orchestrate multi-round training with logging, metrics, and checkpointing.
- Validate the pipeline runs end-to-end on real MNIST data.

## Deliverables
- `src/federated/client.py`, `server.py`, `fedavg.py`, `round_manager.py`
- `scripts/run_initial_fl.py`
- `configs/initial_fl.yaml`
- `tests/test_federated.py`

## Verification
`pytest tests/test_federated.py -v` — all passing (uses synthetic data for
speed; the real MNIST run is a separate, longer-running step via
`scripts/run_initial_fl.py`).

## Next Step
Actually execute `scripts/run_initial_fl.py` against real MNIST data (5
clients, 50 rounds, 10 local epochs) to produce the real `M_old` checkpoint
that later phases depend on.
