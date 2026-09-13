# Phase 6 — Evaluation

**Status: PARTIALLY IMPLEMENTED**

## Goals
- Accuracy (overall + per-client): **implemented**
- Forgetting gap (forget-client accuracy comparison across models): **implemented**
- Membership Inference Attack: **scaffold only** — simple confidence-threshold
  baseline attack; flagged as needing a more sophisticated approach later
- Computation cost (wall-clock time from logged metrics): **implemented**
- Communication cost (round/transmission/byte estimates): **implemented**
- Comparison table (M_old / M_retrain / M_GA / M_unlearn side by side): **implemented**

## Deliverables
- `src/evaluation/accuracy.py`, `forgetting.py`, `mia.py`, `computation.py`,
  `communication.py`, `comparison.py`
- `scripts/run_evaluation.py`, `scripts/run_mia.py`

## Next Step
Once Phases 2-5 have actually been executed and produced real checkpoints,
run `scripts/run_evaluation.py` to populate the real comparison table, and
`scripts/run_mia.py` for the baseline privacy-leakage check. Results should
be written up in `reports/` once available — not before.
