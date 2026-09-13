# Phase 3 — Full-Retraining Baseline

**Status: IMPLEMENTED, NOT YET EXECUTED**

## Goals
- Remove the forget client from the client set.
- Retrain a fresh global model from scratch, using identical FL
  hyperparameters to Phase 2, to produce `M_retrain` — the gold-standard
  reference for evaluating the proposed unlearning method.

## Deliverables
- `src/baselines/full_retraining.py`
- `scripts/run_retraining.py`
- `configs/retraining.yaml`

## Next Step
Run `scripts/run_retraining.py` against the same client partition used in
Phase 2 (`experiments/initial_fl/partition_metadata.json`), once a
`forget_client` has been decided.
