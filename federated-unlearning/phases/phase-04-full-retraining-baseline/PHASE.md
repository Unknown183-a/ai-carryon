# Phase 04 — Full Retraining Baseline

**Status:** Not started
**Depends on:** Phase 03

## Goal

Remove the forget client and retrain the FL system from scratch as the gold-standard reference, `M_retrain`.

## Tasks

- [ ] Implement `src/baselines/full_retraining.py::run_full_retraining`
- [ ] Reuse `FederatedServer` with the forget client excluded from `client_datasets`
- [ ] Save `M_retrain` checkpoint + metrics under `artifacts/experiments/full_retraining/`
- [ ] `configs/unlearning.yaml`'s `full_retraining` section drives its rounds/epochs/lr

## Definition of done

A full retraining run completes and `M_retrain` is checkpointed and evaluable the same way `M_old` is.

## Handoff notes

—
