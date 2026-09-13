"""
Unlearning engine: orchestrates Gradient Ascent + Knowledge Distillation into
a single M_old -> M_unlearn pipeline (blueprint §9).

    Input:  M_old, Forget Client ID, Forget Client Data, Remaining Client
            Data, Configuration
    Output: M_unlearn, Metrics, Logs, Checkpoint

STATUS: this orchestration is implemented and wires together
gradient_ascent.py + knowledge_distillation.py exactly as specified in the
blueprint's architecture diagram. It has NOT yet been run against the actual
trained MNIST checkpoint from experiments/initial_fl/ — that is Phase 4/5
work (see phases/phase04_gradient_ascent.md, phase05_knowledge_distillation.md).
No forgetting/accuracy numbers should be assumed until run_ga_kd.py has
actually been executed and its metrics.csv inspected.
"""
from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Dict

from src.unlearning.gradient_ascent import GradientAscentUnlearner
from src.unlearning.knowledge_distillation import KnowledgeDistiller
from src.utils.checkpoint import save_checkpoint
from src.utils.logging import MetricsLogger, get_logger


def run_unlearning(
    m_old,
    forget_loader,
    remaining_loader,
    config: dict,
    output_dir: str | Path,
    device: str = "cpu",
) -> Dict:
    """
    Full GA + KD unlearning pipeline:
      1. Gradient Ascent on M_old using the forget client's data -> M_GA
      2. Knowledge Distillation: M_old (teacher) -> M_GA-initialized student,
         trained on remaining clients' data -> M_unlearn

    config expects (see configs/ga_kd.yaml):
        unlearning.gradient_ascent.{learning_rate, epochs, momentum}
        unlearning.knowledge_distillation.{learning_rate, epochs, temperature}
    """
    output_dir = Path(output_dir)
    (output_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    logger = get_logger("unlearning_engine", output_dir / "training.log")
    metrics_logger = MetricsLogger(output_dir / "metrics.csv")

    start = time.time()

    # Step 1: Gradient Ascent on the forget client.
    ga_cfg = config["unlearning"]["gradient_ascent"]
    logger.info(f"Starting Gradient Ascent with config: {ga_cfg}")
    ga_unlearner = GradientAscentUnlearner(m_old, ga_cfg)
    ga_result = ga_unlearner.unlearn(forget_loader, device=device)
    logger.info(f"Gradient Ascent done: final_forget_loss={ga_result.final_forget_loss:.4f}, "
                f"epochs_run={ga_result.epochs_run}, time={ga_result.train_time_seconds:.2f}s")

    m_ga = copy.deepcopy(m_old)
    m_ga.load_state_dict(ga_result.state_dict)
    save_checkpoint(m_ga, output_dir / "checkpoints" / "m_ga.pt", extra={"ga_result": vars(ga_result)})

    # Step 2: Knowledge Distillation, teacher=M_old, student initialized from M_GA.
    kd_cfg = config["unlearning"]["knowledge_distillation"]
    logger.info(f"Starting Knowledge Distillation with config: {kd_cfg}")
    distiller = KnowledgeDistiller(student_model=m_ga, teacher_model=m_old, config=kd_cfg)
    kd_result = distiller.distill(remaining_loader, device=device)
    logger.info(f"KD done: final_kd_loss={kd_result.final_kd_loss:.4f}, "
                f"epochs_run={kd_result.epochs_run}, time={kd_result.train_time_seconds:.2f}s")

    m_unlearn = copy.deepcopy(m_old)
    m_unlearn.load_state_dict(kd_result.state_dict)

    total_time = time.time() - start
    save_checkpoint(m_unlearn, output_dir / "checkpoints" / "m_unlearn.pt",
                     extra={"kd_result": vars(kd_result), "total_time_seconds": total_time})

    summary = {
        "gradient_ascent": vars(ga_result),
        "knowledge_distillation": vars(kd_result),
        "total_time_seconds": total_time,
    }
    metrics_logger.log({
        "final_forget_loss": ga_result.final_forget_loss,
        "final_kd_loss": kd_result.final_kd_loss,
        "ga_time_seconds": round(ga_result.train_time_seconds, 3),
        "kd_time_seconds": round(kd_result.train_time_seconds, 3),
        "total_time_seconds": round(total_time, 3),
    })
    logger.info(f"Unlearning engine finished in {total_time:.2f}s.")

    return {"model": m_unlearn, "summary": summary}
