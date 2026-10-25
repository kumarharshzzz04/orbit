"""Shared result contract for model families."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class ModelResult:
    val_probabilities: np.ndarray
    test_probabilities: np.ndarray
    train_probabilities: np.ndarray
    artifact_file: str
    training: dict[str, Any] = field(default_factory=dict)
