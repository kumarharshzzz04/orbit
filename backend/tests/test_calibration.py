from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from ml_sandbox import calibration, config


def _cfg(**training):
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "runs/baseline_live.json").read_text()
    )
    raw = copy.deepcopy(raw)
    raw["training"].update(training)
    return raw


def test_platt_preserves_ranking_and_improves_brier() -> None:
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 2, size=400)
    # Good ranking, badly scaled probabilities (squashed into 0.2-0.5).
    raw = np.clip(labels * 0.25 + rng.normal(0.25, 0.1, size=400), 0.0, 1.0)
    mapped, info = calibration.apply_platt(
        labels, {"val": raw, "test": raw, "train": raw}
    )

    assert info["applied"] is True
    assert 0.0 <= mapped["test"].min() and mapped["test"].max() <= 1.0
    # Strictly monotone: AUC is identical to the raw score AUC.
    assert roc_auc_score(labels, mapped["test"]) == pytest.approx(
        roc_auc_score(labels, raw), abs=1e-12
    )
    brier_raw = float(np.mean((raw - labels) ** 2))
    brier_cal = float(np.mean((mapped["test"] - labels) ** 2))
    assert brier_cal < brier_raw


def test_single_class_validation_is_left_alone() -> None:
    labels = np.ones(50, dtype=np.int64)
    raw = np.linspace(0.1, 0.9, 50)
    mapped, info = calibration.apply_platt(labels, {"val": raw, "test": raw})

    assert info["applied"] is False
    assert np.allclose(mapped["test"], raw)


def test_config_accepts_platt_and_strips_default() -> None:
    cfg = config.RunConfig.from_dict(_cfg(calibration="platt"))
    assert cfg.training["calibration"] == "platt"

    plain = config.RunConfig.from_dict(_cfg())
    assert "calibration" not in plain.training


def test_default_config_hash_is_stable() -> None:
    """Published runs cite this hash; adding an option must not move it."""
    cfg = config.RunConfig.from_dict(_cfg())
    assert cfg.config_hash() == "f542d54c219bb85f7c3ee68d43f7f827dfc58d8f"


def test_unknown_calibration_is_rejected() -> None:
    with pytest.raises(config.ConfigError):
        config.RunConfig.from_dict(_cfg(calibration="isotonic"))
