# Methodology

## Problem

In Federated Learning, multiple clients collaboratively train a global
model without sharing raw data. When a client later requests deletion,
removing its local copy of the data does not remove its influence from
the already-trained global model. Full retraining without that client
is the correct-but-expensive fix.

## Proposed approach

1. Train an initial FL global model, `M_old`, via FedAvg.
2. On a deletion request, select the forget client `Ck`.
3. Compute a full-retraining reference, `M_retrain` (gold standard, expensive).
4. Compute a cheaper alternative, `M_unlearn`, via:
   - **Gradient Ascent** on `Ck`'s data (push the model *away* from fitting it), and
   - **Knowledge Distillation** from `M_old` on the remaining clients' data (preserve
     what the model still legitimately knows).
5. Evaluate `M_unlearn` against `M_retrain` on accuracy, forgetting strength,
   membership-inference resistance, and computation/communication cost.

## Formulas

FedAvg:

W_(t+1) = Σ_k (n_k / n) · W_(t+1)^(k)

Gradient Ascent (vs. normal gradient descent):

- Descent: `W ← W − η∇L`
- Ascent (forgetting): `W ← W + η∇L_forget`

Knowledge Distillation loss (teacher = `M_old`, student = model being unlearned):

`L_KD = KL(P_teacher ‖ P_student)`, at temperature `T` (configurable).

Combined objective (exact weighting is configurable, not hard-coded):

`L_total = λ_forget · L_forget + λ_KD · L_KD`

## Research questions

- RQ1: Can Gradient Ascent reduce the target client's influence on `M_old`?
- RQ2: Can Knowledge Distillation preserve useful knowledge from remaining clients?
- RQ3: How close is `M_unlearn` to `M_retrain`?
- RQ4: How much computation is saved vs. full retraining?
- RQ5: How does data heterogeneity (IID vs. Non-IID) affect unlearning?
- RQ6: Can MIA detect whether the forgotten client's information remains?

## Success criteria

Success is **not** just low forget-client accuracy. A good result shows,
together: strong forgetting, good remaining-client performance, low MIA
membership signal, lower computation, lower communication, and behavior
close to `M_retrain` (with cost ≪ full-retraining cost).
