# Phase 06 — Knowledge Distillation

**Status:** Not started
**Depends on:** Phase 03

## Goal

Implement Knowledge Distillation using `M_old` as teacher, to preserve knowledge from remaining clients while the model is being unlearned.

## Tasks

- [ ] Implement `src/unlearning/knowledge_distillation.py::KnowledgeDistiller.distill`
- [ ] Use `kd_loss` from `src/unlearning/losses.py` (temperature configurable)
- [ ] `configs/unlearning.yaml` → `knowledge_distillation` drives temperature/epochs/lr/lambda
- [ ] Unit test: student accuracy on remaining clients doesn't collapse after distillation

## Definition of done

`KnowledgeDistiller.distill()` runs without error and remaining-client accuracy stays close to `M_old`'s.

## Handoff notes

—
