# Phase 03 — Initial FL Experiment

**Status:** Complete (code); not yet run
**Depends on:** Phase 02

## Goal

Wire client + FedAvg into a full server loop and produce the initial pipeline-validation experiment: 5 clients, 50 rounds, 10 local epochs/round.

## Tasks

- [x] `src/federated/server.py` — round loop, checkpointing, per-round metrics
- [x] `src/federated/round_manager.py` — metrics history + CSV export
- [x] `src/utils/checkpoint.py`, `src/utils/logging.py`, `src/utils/config.py`, `src/utils/seed.py`
- [x] `experiments/run_initial_fl.py` — runnable end-to-end script
- [x] `configs/initial_fl.yaml`
- [ ] Actually run it and commit the resulting `artifacts/experiments/initial_fl/`

## Definition of done

`python experiments/run_initial_fl.py` completes 50 rounds and writes config.yaml, metrics.csv, training.log, partition_metadata.json, and checkpoints/round_*.pt.

## Handoff notes

This produces `M_old` — the checkpoint every later phase (retraining baseline, unlearning) starts from. Run this before starting Phase 04.
