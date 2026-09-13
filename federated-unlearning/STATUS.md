# Status

Source of truth for where the project actually stands. Kept in sync
with `README.md`'s Current Phase checklist above the fold — update
both when a phase finishes.

## Current phase

**Phase 04 — Full Retraining Baseline** (not started)

Phases 00-03 are complete: the data pipeline, model, FedAvg, and the
initial 5-client/50-round/10-local-epoch experiment runner all exist
and are wired together. Phase 08 (Evaluation Framework) is partially
done ahead of schedule — accuracy/cost/comparison utilities exist
since they only depend on Phase 03, not on the unlearning engine.

```
Data pipeline      ██████████ 100%
FL baseline        ██████████ 100%
Evaluation utils   ████░░░░░░  40%   (accuracy/cost/comparison done; forgetting/MIA blocked on unlearning)
Full retraining    ░░░░░░░░░░   0%
Gradient ascent    ░░░░░░░░░░   0%
Knowledge distill. ░░░░░░░░░░   0%
Unlearning engine  ░░░░░░░░░░   0%
MIA                ░░░░░░░░░░   0%
Experiments/report ░░░░░░░░░░   0%
```

## Phase checklist

- [x] Phase 00 — Repo & Skeleton
- [x] Phase 01 — Data Pipeline
- [x] Phase 02 — Model + FedAvg
- [x] Phase 03 — Initial FL Experiment (code complete; not yet run for a real result)
- [ ] Phase 04 — Full Retraining Baseline
- [ ] Phase 05 — Gradient Ascent
- [ ] Phase 06 — Knowledge Distillation
- [ ] Phase 07 — Unlearning Engine
- [ ] Phase 08 — Evaluation Framework (partial — see above)
- [ ] Phase 09 — MIA
- [ ] Phase 10 — Controlled Experiments
- [ ] Phase 11 — Plots + Reports
- [ ] Phase 12 — Final Report / Viva

## Next action

Run `python experiments/run_initial_fl.py --config configs/initial_fl.yaml`
to get a real Phase 03 result into `artifacts/experiments/initial_fl/`,
then start Phase 04 (full retraining baseline) in
`phases/phase-04-full-retraining-baseline/PHASE.md`.
