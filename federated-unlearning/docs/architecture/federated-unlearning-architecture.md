# System Architecture

## Bird's-eye view

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
              │    ┌─────┐ ┌─────┐ ┌─────┐     ┌─────┐   │
              │    │ C1  │ │ C2  │ │ C3  │ ... │ CN  │   │
              │    └──┬──┘ └──┬──┘ └──┬──┘     └──┬──┘   │
              │       └───────┴───────┴───────────┘      │
              │                   │  FedAvg               │
              └───────────────────┬───────────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │  Trained Global │
                         │    Model M_old  │
                         └────────┬────────┘
                                  │  Client requests deletion
                                  ▼
                    ┌─────────────────────────┐
                    │  Select Forget Client Ck │
                    └────────────┬────────────┘
                 ┌───────────────┴────────────────┐
                 ▼                                ▼
       ┌───────────────────┐           ┌────────────────────┐
       │   Forget Client    │           │ Remaining Clients  │
       │       Data         │           │       Data         │
       └─────────┬──────────┘           └─────────┬──────────┘
                 ▼                                ▼
       ┌───────────────────┐           ┌────────────────────┐
       │   Gradient Ascent  │           │ Knowledge           │
       │  (increase loss on │           │ Distillation         │
       │   forget client)   │           │ (preserve knowledge) │
       └─────────┬──────────┘           └─────────┬──────────┘
                 └───────────────┬───────────────┘
                                 ▼
                       ┌────────────────────┐
                       │   Unlearned Model  │
                       │      M_unlearn     │
                       └─────────┬──────────┘
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                  ▼
       ┌──────────────┐  ┌──────────────┐  ┌────────────────┐
       │   Accuracy   │  │     MIA      │  │ Computation &   │
       │   Evaluation │  │  Evaluation  │  │  Communication  │
       └──────────────┘  └──────────────┘  └────────────────┘
               └─────────────────┼──────────────────┘
                                 ▼
                       ┌────────────────────┐
                       │ Compare with Full  │
                       │ Retraining Baseline │
                       │     M_retrain       │
                       └────────────────────┘
```

## Implementation status vs. this diagram

| Stage | Module | Status |
|---|---|---|
| Dataset / Partitioning | `src/data/` | ✅ Implemented |
| Federated Learning (clients, FedAvg, server) | `src/federated/` | ✅ Implemented (initial 5-client/50-round/10-epoch config) |
| Forget-client selection | `src/unlearning/forget_client.py` | ✅ Implemented |
| Full Retraining baseline | `src/baselines/full_retraining.py` | ⏳ Scaffold only (Phase 3) |
| Gradient Ascent | `src/unlearning/gradient_ascent.py` | ⏳ Scaffold only (Phase 4) |
| Knowledge Distillation | `src/unlearning/knowledge_distillation.py` | ⏳ Scaffold only (Phase 5) |
| Accuracy evaluation | `src/evaluation/accuracy.py` | ✅ Implemented |
| Computation / Communication cost | `src/evaluation/computation.py`, `communication.py` | ✅ Implemented |
| MIA evaluation | `src/evaluation/mia.py` | ⏳ Scaffold only (Phase 6) |
| Model comparison table | `src/evaluation/comparison.py` | ✅ Implemented (populates only real metrics) |

## Module boundaries

```text
src/
├── data/         # dataset loading + client partitioning (IID / Non-IID)
├── models/       # model architectures
├── federated/    # client, server, FedAvg, round tracking  -> produces M_old
├── unlearning/   # forget-client selection, Gradient Ascent, KD, engine -> M_unlearn
├── baselines/    # full retraining -> M_retrain (gold standard reference)
├── evaluation/   # accuracy, forgetting, MIA, cost, comparison table
└── utils/        # config, logging, checkpointing, seeding (shared everywhere)
```

Flower is not currently used; if introduced later it will be isolated
behind `src/federated/` so the rest of the codebase stays framework-agnostic.
