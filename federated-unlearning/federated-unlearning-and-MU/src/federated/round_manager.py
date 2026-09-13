"""
Round manager: orchestrates the full multi-round FL training loop and wires
together server + logging + checkpointing + metrics.

This is the piece `scripts/run_initial_fl.py` calls; it exists as its own
module (rather than being inlined in the script) so the same orchestration
logic can be reused by the full-retraining baseline (blueprint §12), which
runs an identical loop, just on a client set with the forget-client removed.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from src.federated.server import FederatedServer
from src.utils.checkpoint import save_checkpoint
from src.utils.logging import MetricsLogger, get_logger


def run_federated_training(
    server: FederatedServer,
    test_loader,
    rounds: int,
    local_epochs: int,
    lr: float,
    momentum: float,
    output_dir: str | Path,
    checkpoint_every: int = 10,
    run_name: str = "federated_training",
) -> Dict:
    """
    Run `rounds` communication rounds of federated averaging, logging and
    checkpointing along the way. Returns a summary dict.

    Every experiment produces (blueprint §6, §22):
      output_dir/training.log
      output_dir/metrics.csv
      output_dir/checkpoints/round_{i}.pt
      output_dir/checkpoints/final.pt
    """
    output_dir = Path(output_dir)
    (output_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    logger = get_logger(run_name, output_dir / "training.log")
    metrics_logger = MetricsLogger(output_dir / "metrics.csv")

    logger.info(f"Starting {run_name}: {rounds} rounds, {local_epochs} local epochs/round, "
                f"{len(server.clients)} clients")

    start_time = time.time()
    history: List[Dict] = []

    for round_idx in range(1, rounds + 1):
        round_start = time.time()

        client_results = server.broadcast_and_train_round(local_epochs=local_epochs, lr=lr, momentum=momentum)
        server.aggregate(client_results)
        eval_metrics = server.evaluate(test_loader)

        round_time = time.time() - round_start
        avg_client_loss = sum(r.train_loss for r in client_results) / len(client_results)
        avg_client_acc = sum(r.train_accuracy for r in client_results) / len(client_results)

        row = {
            "round": round_idx,
            "avg_client_train_loss": round(avg_client_loss, 6),
            "avg_client_train_accuracy": round(avg_client_acc, 6),
            "test_loss": round(eval_metrics["test_loss"], 6),
            "test_accuracy": round(eval_metrics["test_accuracy"], 6),
            "round_time_seconds": round(round_time, 3),
        }
        metrics_logger.log(row)
        history.append(row)

        logger.info(
            f"Round {round_idx}/{rounds} | "
            f"train_loss={avg_client_loss:.4f} train_acc={avg_client_acc:.4f} | "
            f"test_loss={eval_metrics['test_loss']:.4f} test_acc={eval_metrics['test_accuracy']:.4f} | "
            f"{round_time:.2f}s"
        )

        if checkpoint_every and round_idx % checkpoint_every == 0:
            save_checkpoint(
                server.global_model,
                output_dir / "checkpoints" / f"round_{round_idx}.pt",
                extra={"round": round_idx, "metrics": row},
            )

    total_time = time.time() - start_time
    save_checkpoint(
        server.global_model,
        output_dir / "checkpoints" / "final.pt",
        extra={"round": rounds, "metrics": history[-1] if history else None},
    )

    logger.info(f"Finished {run_name} in {total_time:.2f}s. Final test accuracy: "
                f"{history[-1]['test_accuracy'] if history else 'N/A'}")

    return {
        "history": history,
        "total_time_seconds": total_time,
        "final_metrics": history[-1] if history else None,
    }
