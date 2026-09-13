# Phase 07 — Unlearning Engine

**Status:** Not started
**Depends on:** Phase 05, Phase 06

## Goal

Combine Gradient Ascent + Knowledge Distillation into the end-to-end unlearning pipeline that produces `M_unlearn`.

## Tasks

- [ ] Implement `src/unlearning/engine.py::UnlearningEngine.run`
- [ ] Calls `GradientAscentUnlearner` then `KnowledgeDistiller` per blueprint Section 9
- [ ] Save `M_unlearn` checkpoint + metrics under `artifacts/experiments/unlearning_ga_kd/`
- [ ] Use `src/unlearning/forget_client.py` for client selection (already implemented)

## Definition of done

`UnlearningEngine.run()` returns an `UnlearningResult` with a checkpointed `M_unlearn` and recorded metrics.

## Handoff notes

—
