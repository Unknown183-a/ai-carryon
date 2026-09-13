# Federated Unlearning via Gradient Ascent + Knowledge Distillation

A research/course project studying how to make a federated-learning client's
data "forgettable" from an already-trained global model, without paying the
full cost of retraining from scratch.

## Current Status

**Implemented and exercised (real code, real tests, real run possible today):**
- MNIST loading + IID/Non-IID client partitioning (`src/data/`)
- Small CNN model (`src/models/cnn.py`)
- Federated Averaging (`src/federated/`) — client-side local training, server
  aggregation, round orchestration with logging/checkpointing
- `scripts/prepare_data.py` + `scripts/run_initial_fl.py` — runnable end-to-end
- Unit test suite: **18/18 passing** (`pytest tests/`)

**Implemented, NOT yet experimentally run/validated:**
- Full-retraining baseline (`src/baselines/full_retraining.py`)
- Gradient Ascent unlearning (`src/unlearning/gradient_ascent.py`)
- Knowledge Distillation (`src/unlearning/knowledge_distillation.py`)
- Combined GA+KD unlearning engine (`src/unlearning/engine.py`)
- Accuracy / forgetting / computation / communication / comparison-table
  evaluation (`src/evaluation/`)

These pass unit tests confirming they run correctly and produce valid,
loadable checkpoints — but **no forgetting-quality, accuracy-tradeoff, or
cost numbers exist yet**. Producing those requires running the actual 50-round
MNIST experiment (`scripts/run_initial_fl.py`), then the retraining baseline
and GA/KD scripts against that real checkpoint. Do not treat anything not
present in a generated `experiments/*/summary.json` as a real result.

**Scaffold only:**
- Membership Inference Attack evaluation (`src/evaluation/mia.py`) — a simple
  confidence-threshold baseline attack; flagged in the blueprint as needing a
  more sophisticated treatment later.

See `docs/methodology.md` for the full formulation and research questions,
and `docs/architecture.md` for the module map and data-flow diagram.

## Repository Structure

```text
federated-unlearning/
├── configs/              # YAML configs (base + per-experiment overrides)
├── src/
│   ├── data/              # MNIST loading, IID/Non-IID partitioning
│   ├── models/             # CNN definition
│   ├── federated/           # Client, server, FedAvg, round orchestration
│   ├── baselines/            # Full-retraining baseline
│   ├── unlearning/            # Gradient Ascent, Knowledge Distillation, engine
│   ├── evaluation/             # Accuracy, forgetting, MIA, cost, comparison
│   └── utils/                   # Config loading, logging, checkpointing, seeding
├── scripts/               # CLI entry points (one per experiment/phase)
├── experiments/            # Per-run outputs: config, logs, metrics, checkpoints
├── tests/                    # pytest unit tests
├── docs/                      # Architecture + methodology writeups
├── phases/                     # Phase-by-phase implementation plan
└── reports/                     # Results write-ups (populated as experiments run)
```

## Quickstart

```bash
pip install -r requirements.txt

# 1. Download MNIST + create the 5-client partition
python scripts/prepare_data.py --config configs/initial_fl.yaml

# 2. Run the initial FL experiment (50 rounds, 10 local epochs, FedAvg)
python scripts/run_initial_fl.py --config configs/initial_fl.yaml

# 3. Run the full-retraining baseline (excludes the forget client)
python scripts/run_retraining.py --config configs/retraining.yaml

# 4. Run the proposed unlearning pipeline (Gradient Ascent + KD)
python scripts/run_ga_kd.py --config configs/ga_kd.yaml

# 5. Assemble the comparison table across whatever checkpoints exist
python scripts/run_evaluation.py --partition-metadata experiments/initial_fl/partition_metadata.json
```

Run the test suite any time with:

```bash
pytest tests/ -q
```

## Design Principles

- **Nothing hard-coded.** Every experiment is fully described by a YAML
  config (`configs/*.yaml`), merged on top of `configs/base.yaml`.
- **Reproducibility.** Every run seeds all RNGs, snapshots the software
  environment, and persists its exact config alongside its results.
- **Fair comparison.** The full-retraining baseline reuses the identical
  FL orchestration code (`src/federated/round_manager.py`) as the initial
  experiment — same architecture, same hyperparameters, same client
  partition — so it's a fair reference point for the proposed method.
- **No fabricated results.** Evaluation code leaves a metric as `None`/missing
  rather than guessing, until the corresponding experiment has actually run.

## License

MIT — see `LICENSE`.
