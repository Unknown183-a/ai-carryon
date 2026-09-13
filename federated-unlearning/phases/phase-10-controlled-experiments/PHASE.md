# Phase 10 — Controlled Experiments

**Status:** Not started
**Depends on:** Phase 04, Phase 07, Phase 09

## Goal

Small, deliberate grid over client count, IID/Non-IID, and unlearning hyperparameters — not a blind full sweep.

## Tasks

- [ ] Client count: 5 / 10 / 20 (only what's computationally feasible)
- [ ] Data distribution: IID vs Non-IID
- [ ] Unlearning methods: Original / Full Retraining / Gradient Ascent / GA+KD
- [ ] Hyperparameters: GA lr/epochs, KD weight/temperature, local epochs, FL rounds — small controlled grid, not exhaustive

## Definition of done

Each configuration in the grid has a saved config, checkpoint, and metrics under its own `artifacts/experiments/<name>/`.

## Handoff notes

—
