# Federated Unlearning

Federated Learning trains a shared model across clients without
pooling raw data. This project studies how to make a trained
federated model efficiently "forget" one client's contribution —
via Gradient Ascent + Knowledge Distillation — without paying the
cost of retraining from scratch.

This repo is a **holder / scaffold** — the folder shape and phase
briefs are already set up so that whoever opens it next (including
future-you) can go straight to their segment and start working, with
zero setup.

## Current Phase

*(Kept in sync with `STATUS.md` — that file is the source of truth; this is just a glance.)*

- [x] Phase 00 — Repo & Skeleton
- [x] Phase 01 — Data Pipeline
- [x] Phase 02 — Model + FedAvg
- [x] Phase 03 — Initial FL Experiment (code complete; not yet run)
- [ ] Phase 04 — Full Retraining Baseline
- [ ] Phase 05 — Gradient Ascent
- [ ] Phase 06 — Knowledge Distillation
- [ ] Phase 07 — Unlearning Engine
- [ ] Phase 08 — Evaluation Framework (partial)
- [ ] Phase 09 — MIA
- [ ] Phase 10 — Controlled Experiments
- [ ] Phase 11 — Plots + Reports
- [ ] Phase 12 — Final Report / Viva

**Progress**

```
Data pipeline      ██████████ 100%
FL baseline        ██████████ 100%
Evaluation utils   ████░░░░░░  40%
Unlearning         ░░░░░░░░░░   0%
Experiments/report ░░░░░░░░░░   0%
```

## Where to look

| I want to... | Go to |
|---|---|
| Understand *why* the system is designed this way | [`docs/architecture/federated-unlearning-architecture.md`](docs/architecture/federated-unlearning-architecture.md) — bird's-eye diagram + module status |
| Understand the approach and formulas (FedAvg, GA, KD) | [`docs/methodology.md`](docs/methodology.md) |
| Understand *what to build next* and the full phase order | [`BUILD_GUIDE.md`](BUILD_GUIDE.md) — the single working copy, edit this if the plan changes |
| See where the project currently stands | [`STATUS.md`](STATUS.md) |
| Work on one specific phase | [`phases/`](phases/) — each phase has its own self-contained `PHASE.md` |
| Log what I actually did | [`work-reports/`](work-reports/) — `daily/` each session, `weekly/` roll-ups, `milestones/` on phase completion |
| Run the initial FL experiment | `python experiments/run_initial_fl.py --config configs/initial_fl.yaml` |
| Run tests | `pytest tests/` |

## How this repo is organized

- `docs/architecture/` — bird's-eye diagram + implementation-status table (reference, explains *why*). `docs/api/`, `docs/decisions/`, `docs/deployment/`, `docs/diagrams/` are optional, fill in as needed (see each folder's `README.md`).
- `BUILD_GUIDE.md` (root) — the one living build-order document; edit this if scope/order changes, then re-derive `phases/*/PHASE.md` from it
- `phases/phase-00-...` through `phases/phase-12-...` — one folder per build phase, each with a `PHASE.md` containing that phase's Goal, Depends On, Tasks, Definition of Done, and Handoff Notes
- `src/` — organized by **responsibility**, not technology: `data/`, `models/`, `federated/`, `unlearning/`, `baselines/`, `evaluation/`, `utils/`
- `configs/` — every experiment parameter lives here (YAML), never hard-coded in `src/`
- `experiments/`, `tests/`, `artifacts/` — runnable scripts, unit tests, and experiment outputs (configs/checkpoints/metrics/logs) respectively

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## No fabricated results

Numbers only ever come from `artifacts/experiments/*/metrics.csv`
after an actual run. Modules not yet implemented raise
`NotImplementedError` pointing at the phase that will fill them in —
see `STATUS.md`.

## The rule

Whoever stops mid-phase, before stopping:

1. Ticks every checkbox actually finished in that phase's `PHASE.md`.
2. Writes 2-5 sentences in that phase's **Handoff Notes**.
3. Updates `STATUS.md` (and the Current Phase checklist above, if a phase just finished).
4. Adds one file to `work-reports/daily/` for the session (copy `work-reports/daily/TEMPLATE.md`).

Follow that and no handoff call is ever needed — just open your `PHASE.md` and continue.
