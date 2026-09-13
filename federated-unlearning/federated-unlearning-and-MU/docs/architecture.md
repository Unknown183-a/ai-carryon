# System Architecture

## Complete System Flow

```text
                         ┌─────────────────────┐
                         │       MNIST         │
                         │      Dataset        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Data Partitioning │
                         │     IID / Non-IID   │
                         └──────────┬──────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │          Federated Learning              │
              │    C1  C2  C3 ... CN   →  FedAvg          │
              └───────────────────┬─────────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │  Trained Global │
                         │    Model M_old  │  ◄── COMPLETED (see README)
                         └────────┬────────┘
                                  │  Client requests deletion
                                  ▼
                    ┌─────────────────────────┐
                    │  Select Forget Client Ck │
                    └────────────┬────────────┘
                 ┌───────────────┴────────────────┐
                 ▼                                ▼
       ┌───────────────────┐           ┌────────────────────┐
       │   Forget Client   │           │ Remaining Clients  │
       │       Data        │           │       Data         │
       └─────────┬─────────┘           └─────────┬──────────┘
                 ▼                               ▼
       ┌───────────────────┐           ┌────────────────────┐
       │   Gradient Ascent │           │ Knowledge           │
       │ (increase forget  │           │ Distillation        │
       │  client's loss)   │           │ (preserve knowledge)│
       └─────────┬─────────┘           └─────────┬──────────┘
                 └───────────────┬───────────────┘
                                 ▼
                       ┌────────────────────┐
                       │   Unlearned Model  │  ◄── PLANNED (implemented,
                       │      M_unlearn     │       not yet experimentally run)
                       └─────────┬──────────┘
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                  ▼
       ┌──────────────┐  ┌──────────────┐  ┌────────────────┐
       │   Accuracy   │  │     MIA      │  │ Computation &  │
       │   Evaluation │  │ Evaluation   │  │ Communication  │
       └──────────────┘  └──────────────┘  └────────────────┘
               └─────────────────┼──────────────────┘
                                 ▼
                       ┌────────────────────┐
                       │ Compare with Full  │
                       │ Retraining Baseline │
                       │     M_retrain      │
                       └────────────────────┘
```

## Module Map

| Module | Path | Status |
|---|---|---|
| Data Management | `src/data/` | Implemented, exercised (MNIST prep + partitioning) |
| Model | `src/models/cnn.py` | Implemented, exercised |
| Federated Learning | `src/federated/` | Implemented, exercised (initial 50-round experiment) |
| Full-Retraining Baseline | `src/baselines/full_retraining.py` | Implemented, not yet run |
| Unlearning Engine (GA + KD) | `src/unlearning/` | Implemented, not yet run against a real M_old |
| Evaluation — Accuracy | `src/evaluation/accuracy.py` | Implemented, exercised |
| Evaluation — Forgetting | `src/evaluation/forgetting.py` | Implemented, not yet run |
| Evaluation — MIA | `src/evaluation/mia.py` | Scaffold (simple baseline attack) |
| Evaluation — Computation/Comm cost | `src/evaluation/computation.py`, `communication.py` | Implemented, not yet run |
| Evaluation — Comparison table | `src/evaluation/comparison.py` | Implemented |

See `README.md` → "Current Status" for what has actually been executed vs. what is implemented-but-unvalidated vs. what is future work.

## Data Flow: Config-Driven Design

Every script (`scripts/run_*.py`) takes a `--config path/to/x.yaml`. Configs are
merged on top of `configs/base.yaml` (see `src/utils/config.py`) so no
experiment parameter is hard-coded in Python. Every run persists:

```text
experiments/<run_name>/
├── config.yaml          # exact config used
├── training.log          # human-readable log
├── metrics.csv           # per-round/per-step structured metrics
├── summary.json           # final result summary
└── checkpoints/           # model checkpoints (M_old, M_GA, M_unlearn, ...)
```
