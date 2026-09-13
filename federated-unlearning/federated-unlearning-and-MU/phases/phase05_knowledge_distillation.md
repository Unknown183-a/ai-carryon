# Phase 5 — Knowledge Distillation (Knowledge Preservation)

**Status: IMPLEMENTED, NOT YET EXECUTED**

## Goals
- Use `M_old` as a frozen teacher and `M_GA` as the student's starting point.
- Distill on the *remaining* clients' data to recover/preserve accuracy that
  pure gradient ascent may have damaged, producing `M_unlearn`.

## Deliverables
- `src/unlearning/knowledge_distillation.py`
- `src/unlearning/engine.py` (wires GA + KD into one pipeline)
- `scripts/run_ga_kd.py`
- `configs/ga_kd.yaml`

## Next Step
Run the full pipeline end-to-end on real data and inspect the resulting
`M_unlearn` checkpoint's accuracy on both the forget client and the
remaining clients.
