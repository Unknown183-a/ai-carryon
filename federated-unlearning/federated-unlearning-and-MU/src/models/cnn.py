"""
Model definition (Module B — blueprint §7).

Small CNN for MNIST, matching blueprint guidance: "Use a small CNN initially."
Kept intentionally simple/shallow since the research focus of this project is
the unlearning procedure, not model architecture.
"""
from __future__ import annotations


def build_model(num_classes: int = 10):
    """Factory so config can eventually select between architectures."""
    import torch.nn as nn

    class SmallCNN(nn.Module):
        def __init__(self, num_classes: int = 10):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 16, kernel_size=3, padding=1),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),  # 28x28 -> 14x14
                nn.Conv2d(16, 32, kernel_size=3, padding=1),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),  # 14x14 -> 7x7
            )
            self.classifier = nn.Sequential(
                nn.Flatten(),
                nn.Linear(32 * 7 * 7, 128),
                nn.ReLU(inplace=True),
                nn.Dropout(0.25),
                nn.Linear(128, num_classes),
            )

        def forward(self, x):
            x = self.features(x)
            return self.classifier(x)

        def logits(self, x):
            """Explicit alias used by KD/GA modules that need raw logits
            (as opposed to a probability distribution) for their loss terms."""
            return self.forward(x)

    return SmallCNN(num_classes=num_classes)


def count_parameters(model) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_flat_params(model):
    """Flatten all model parameters into a single 1D tensor (useful for
    measuring communication cost in bytes, blueprint §13.F)."""
    import torch

    return torch.cat([p.detach().flatten() for p in model.parameters()])


def model_size_bytes(model) -> int:
    """Approximate size, in bytes, of one full model transmission."""
    return sum(p.numel() * p.element_size() for p in model.parameters())
