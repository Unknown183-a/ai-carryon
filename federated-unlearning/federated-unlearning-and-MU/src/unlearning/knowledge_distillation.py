"""
Knowledge Distillation for knowledge preservation (blueprint §11).

    M_old (teacher, frozen)
         |  soft predictions
         v
    Remaining Client Data -> Student Model
         |
         v
      M_unlearn

STATUS: implemented per blueprint's formula. Not yet experimentally
validated (see docs/methodology.md and README "Current Status").
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class DistillationResult:
    state_dict: Dict
    final_kd_loss: float
    epochs_run: int
    train_time_seconds: float


class KnowledgeDistiller:
    def __init__(self, student_model, teacher_model, config: dict):
        """
        config keys:
          - learning_rate: float
          - epochs: int
          - temperature: float
          - momentum: float (optional, default 0.9)
        """
        self.student_model = student_model
        self.teacher_model = teacher_model
        self.config = config

    def distill(self, remaining_loader, device: str = "cpu") -> DistillationResult:
        import torch
        import torch.optim as optim

        from src.unlearning.losses import kd_loss

        student = copy.deepcopy(self.student_model).to(device)
        student.train()

        teacher = self.teacher_model.to(device)
        teacher.eval()
        for p in teacher.parameters():
            p.requires_grad_(False)

        lr = self.config["learning_rate"]
        epochs = self.config["epochs"]
        temperature = self.config.get("temperature", 4.0)
        momentum = self.config.get("momentum", 0.9)

        optimizer = optim.SGD(student.parameters(), lr=lr, momentum=momentum)

        start = time.time()
        last_loss = None
        epochs_run = 0

        for epoch in range(epochs):
            epochs_run = epoch + 1
            for x, _y in remaining_loader:
                x = x.to(device)
                optimizer.zero_grad()

                with torch.no_grad():
                    teacher_logits = teacher(x)
                student_logits = student(x)

                loss = kd_loss(student_logits, teacher_logits, temperature=temperature)
                loss.backward()
                optimizer.step()
                last_loss = loss.item()

        elapsed = time.time() - start
        return DistillationResult(
            state_dict=copy.deepcopy(student.state_dict()),
            final_kd_loss=last_loss if last_loss is not None else float("nan"),
            epochs_run=epochs_run,
            train_time_seconds=elapsed,
        )
