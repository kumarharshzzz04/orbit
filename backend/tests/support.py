"""Shared helpers for ML sandbox tests (tiny, fast configs)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

N_TARGETS = 140
STUB_SEED = 7

BASELINE_PARAMS: dict[str, Any] = {
    "n_estimators": 60,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.9,
    "min_samples_leaf": 4,
    "class_weight": None,
}

HIST_PARAMS: dict[str, Any] = {
    "max_iter": 80,
    "learning_rate": 0.05,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 10,
    "l2_regularization": 1.0,
    "class_weight": None,
}

CNN_PARAMS: dict[str, Any] = {
    "channels": [16, 32, 48],
    "kernel_size": 5,
    "dropout": 0.2,
    "fc_dim": 32,
    "class_weight": None,
}

BASELINE_TRAINING: dict[str, Any] = {
    "threshold_selection": "val_f1",
    "threshold": 0.5,
}

CNN_TRAINING: dict[str, Any] = {
    "threshold_selection": "val_f1",
    "threshold": 0.5,
    "max_epochs": 2,
    "batch_size": 32,
    "learning_rate": 0.001,
    "weight_decay": 0.0001,
    "patience": 2,
    "num_threads": 2,
    "max_train_seconds": 120.0,
    "augmentation": {"phase_shift": False, "noise_ppm": 0.0},
}


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def make_config(
    root: str | Path,
    *,
    model: str = "baseline",
    name: str = "test-run",
    **overrides: Any,
) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "name": name,
        "model": model,
        "seed": 42,
        "hypothesis_id": None,
        "data": {
            "mode": "stub",
            "root": str(root),
            "n_bins": 400,
            "split_version": "v1",
            "stub_targets": N_TARGETS,
            "stub_seed": STUB_SEED,
            "verify_content": True,
        },
        "features": {"set": "catalog_v1"},
        "model_params": copy.deepcopy(
            {
                "baseline": BASELINE_PARAMS,
                "hist": HIST_PARAMS,
            }.get(model, CNN_PARAMS)
        ),
        "training": copy.deepcopy(
            BASELINE_TRAINING if model in {"baseline", "hist"} else CNN_TRAINING
        ),
    }
    deep_update(raw, overrides)
    return raw


def write_config(path: str | Path, raw: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return destination
