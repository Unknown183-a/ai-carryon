# Phase 4 — Gradient Ascent Unlearning

**Status: IMPLEMENTED, NOT YET EXECUTED**

## Goals
- Take the trained `M_old` and the forget client's data.
- Run gradient ASCENT (rather than descent) on the forget client's loss to
  increase the model's loss on that client's data, producing `M_GA`.

## Deliverables
- `src/unlearning/gradient_ascent.py`
- `src/unlearning/losses.py` (forget loss term)
- `src/unlearning/forget_client.py` (forget-client selection)
- `scripts/run_gradient_ascent.py`
- `configs/gradient_ascent.yaml`
- `tests/test_unlearning.py` (confirms it runs + produces a loadable model)

## Next Step
Run against the real `M_old` checkpoint from Phase 2, then inspect
`experiments/gradient_ascent/summary.json` for the actual forget-loss
trajectory before drawing any conclusions about forgetting quality.
