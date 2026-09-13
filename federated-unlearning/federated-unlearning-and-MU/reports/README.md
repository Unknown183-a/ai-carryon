# Reports

This directory holds results write-ups, populated as experiments are
actually run — not before. Each report should cite the exact
`experiments/<run_name>/summary.json` and `metrics.csv` it draws from, so
every number is traceable back to a real run.

## Planned Reports (not yet written — no experiments have been run beyond
the pipeline-validation stage described in the top-level README)

- `01_initial_fl_results.md` — MNIST FL pipeline validation: convergence
  curve, final accuracy, per-round timing.
- `02_full_retraining_baseline.md` — `M_retrain` accuracy and cost.
- `03_gradient_ascent_results.md` — forget-loss trajectory, forget-client
  accuracy drop, remaining-client accuracy impact.
- `04_ga_kd_results.md` — full unlearning pipeline results vs. `M_retrain`.
- `05_mia_evaluation.md` — baseline membership-inference attack accuracy.
- `06_iid_vs_non_iid.md` — RQ5: how data heterogeneity affects unlearning.
- `07_final_comparison.md` — the full comparison table (blueprint §14) with
  discussion against the stated success criteria (`docs/methodology.md`).
