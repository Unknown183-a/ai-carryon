# Phase 09 — MIA

**Status:** Not started
**Depends on:** Phase 07, Phase 08

## Goal

Membership Inference Attack: evaluate whether the forgotten client's samples remain distinguishable as training members after unlearning.

## Tasks

- [ ] Choose an MIA methodology (confidence-threshold or shadow-model)
- [ ] Implement `src/evaluation/mia.py::run_mia`
- [ ] Run against `M_old`, `M_retrain`, and `M_unlearn` for comparison

## Definition of done

MIA score is computed and recorded in the comparison table for all three models.

## Handoff notes

—
