# Phase 05 — Gradient Ascent

**Status:** Not started
**Depends on:** Phase 03

## Goal

Implement the Gradient Ascent unlearner: push the model away from fitting the forget client's data.

## Tasks

- [ ] Implement `src/unlearning/gradient_ascent.py::GradientAscentUnlearner.unlearn`
- [ ] Use `gradient_ascent_loss` from `src/unlearning/losses.py`
- [ ] lr, epochs, batch size all config-driven (`configs/unlearning.yaml` → `gradient_ascent`)
- [ ] Unit test: forget-client loss increases after `unlearn()`

## Definition of done

`GradientAscentUnlearner.unlearn()` runs without error and measurably increases loss on the forget client's data.

## Handoff notes

—
