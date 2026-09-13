# Phase 08 — Evaluation Framework

**Status:** Partial
**Depends on:** Phase 03 (accuracy/cost); Phase 07 (forgetting)

## Goal

Metrics to compare `M_old`, `M_retrain`, and `M_unlearn`: accuracy, forgetting strength, computation/communication cost.

## Tasks

- [x] `src/evaluation/accuracy.py` — overall + per-client accuracy
- [x] `src/evaluation/computation.py` — wall-clock timing helper
- [x] `src/evaluation/communication.py` — model size / approximate bytes transferred
- [x] `src/evaluation/comparison.py` — builds the comparison table CSV, blank for un-run metrics
- [ ] `src/evaluation/forgetting.py` — needs `M_unlearn` from Phase 07

## Definition of done

Comparison table populates real numbers for every phase that has actually been run; blank (not fabricated) otherwise.

## Handoff notes

Forgetting is intentionally blocked on Phase 07 — see `src/evaluation/forgetting.py` docstring.
