# Methodology

## Problem

In Federated Learning, multiple clients collaboratively train a global model
without sharing raw training data. After training, a client may request
deletion/unlearning. Deleting the client's local data does not remove its
influence from the already-trained global model. The ideal solution is to
retrain the entire FL system without that client, but this can be
computationally and communication expensive.

## Proposed Solution

1. Initial Federated Learning → `M_old`
2. Forget-client selection
3. Full-retraining baseline → `M_retrain` (gold-standard reference)
4. Gradient Ascent for forgetting → `M_GA`
5. Knowledge Distillation for preserving useful knowledge → `M_unlearn`
6. Evaluation against the full-retraining reference

Core idea: Gradient Ascent makes the model forget the target client, while
Knowledge Distillation helps preserve useful knowledge from the remaining
clients.

## Formulations

**FedAvg:**

```
W_{t+1} = Σ_k (n_k / n) · W_{t+1}^{(k)}
```

**Gradient Ascent** (forgetting step, vs. normal descent `W ← W - η∇L`):

```
W ← W + η∇L_forget
```

Implemented as SGD on the negated forget loss (mathematically equivalent,
reuses standard optimizers) — see `src/unlearning/gradient_ascent.py`.

**Knowledge Distillation:**

```
L_KD = KL(P_teacher ‖ P_student)     (at temperature T)
```

**Combined objective:**

```
L_total = λ_forget · L_forget + λ_KD · L_KD
```

All λ, T, learning rates, and epoch counts are configuration-driven
(`configs/gradient_ascent.yaml`, `configs/ga_kd.yaml`) rather than hard-coded,
so they can be swept as part of the hyperparameter study (blueprint
Experiment Group D).

## Research Questions

- **RQ1** — Can Gradient Ascent reduce the target client's influence on a trained FL model?
- **RQ2** — Can Knowledge Distillation preserve useful knowledge from remaining clients?
- **RQ3** — How close is the proposed unlearned model to full retraining?
- **RQ4** — How much computation can be saved compared with full retraining?
- **RQ5** — How does data heterogeneity (IID vs Non-IID) affect unlearning?
- **RQ6** — Can MIA detect whether the target client's information remains in the model?

## Success Criteria

Success is **not** defined only as low forget-client accuracy. A successful
method should ideally demonstrate, simultaneously:

```
Strong Forgetting
        +
Good Remaining-Client Performance
        +
Low MIA Membership Signal
        +
Lower Computation
        +
Lower Communication
        +
Behavior Similar to M_retrain
```

Final conceptual target: `M_unlearn ≈ M_retrain`, with `Cost_unlearn ≪ Cost_retrain`.

## What Has and Hasn't Been Validated

The Gradient Ascent and Knowledge Distillation implementations follow the
formulas above exactly and pass unit tests confirming they run correctly and
produce loadable model checkpoints (`tests/test_unlearning.py`). **No
forgetting-quality, MIA, or cost numbers have been produced yet** — that
requires running `scripts/run_gradient_ascent.py` / `run_ga_kd.py` /
`run_mia.py` against the real trained `M_old` checkpoint and inspecting the
resulting `metrics.csv` / `summary.json` files. Do not treat any numbers not
present in `experiments/*/summary.json` as real results.
