# Build Guide

The single working copy of the build order. Edit this if scope or
phase order changes, then re-derive the affected `phases/*/PHASE.md`
from it. `STATUS.md` tracks where the project actually is right now;
this file describes the plan.

## Phase order

| Phase | Name | Depends on | Deliverable |
|---|---|---|---|
| 00 | Repo & Skeleton | — | Repo structure, configs, requirements, docs scaffold |
| 01 | Data Pipeline | 00 | MNIST loading + IID/Non-IID client partitioning |
| 02 | Model + FedAvg | 01 | CNN model, federated client, FedAvg aggregation |
| 03 | Initial FL Experiment | 02 | 5-client/50-round/10-epoch run producing `M_old`, checkpoints, metrics |
| 04 | Full Retraining Baseline | 03 | Forget-client removal + retrain-from-scratch, producing `M_retrain` |
| 05 | Gradient Ascent | 03 | `GradientAscentUnlearner` implemented and unit-tested |
| 06 | Knowledge Distillation | 03 | `KnowledgeDistiller` implemented and unit-tested |
| 07 | Unlearning Engine | 05, 06 | Combined GA+KD pipeline producing `M_unlearn` |
| 08 | Evaluation Framework | 03 | Accuracy, forgetting, computation/communication cost, comparison table |
| 09 | MIA | 07, 08 | Membership Inference Attack evaluation on `M_unlearn` vs `M_retrain` |
| 10 | Controlled Experiments | 04, 07, 09 | Small grid over client count, IID/Non-IID, hyperparameters |
| 11 | Plots + Reports | 10 | Plot generation scripts, populated comparison tables |
| 12 | Final Report / Viva | 11 | Final report template, viva Q&A, biweekly report templates |

## Ground rules (apply to every phase)

1. Do not invent experimental results — read them from `artifacts/experiments/*/metrics.csv` after an actual run, or leave the field blank.
2. Every experiment parameter (client count, rounds, epochs, lr, forget client, temperature, etc.) comes from a `configs/*.yaml` file — never hard-coded.
3. Every experiment saves its config, checkpoints, logs, and metrics under `artifacts/experiments/<name>/`.
4. Keep previous phases' functionality working — this is additive, not a rewrite each phase.
5. Compare models fairly: same architecture, same evaluation data.
