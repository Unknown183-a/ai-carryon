"""
Reproducibility utilities: seeding and environment snapshotting.

Blueprint §22 requires every experiment to set random seeds and record the
software environment where practical.
"""
from __future__ import annotations

import platform
import random
import sys
from typing import Any, Dict

import numpy as np


def set_seed(seed: int) -> None:
    """Seed python, numpy, and torch (CPU + CUDA) RNGs for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        # Prefer determinism over raw speed for research reproducibility.
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        # torch may not be installed yet at some stages of setup (e.g. CI
        # linting steps); seeding python/numpy still happens above.
        pass


def snapshot_environment() -> Dict[str, Any]:
    """Capture basic environment info to store alongside experiment results."""
    info: Dict[str, Any] = {
        "python_version": sys.version,
        "platform": platform.platform(),
    }
    try:
        import torch

        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_device_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch_version"] = None
        info["cuda_available"] = False
    try:
        import torchvision

        info["torchvision_version"] = torchvision.__version__
    except ImportError:
        info["torchvision_version"] = None
    return info
