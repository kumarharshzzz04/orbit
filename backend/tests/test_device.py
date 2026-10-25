from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ml_sandbox import config


def _cnn_config(**training):
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "runs/cnn_live.json").read_text()
    )
    raw = copy.deepcopy(raw)
    raw["training"].update(training)
    return raw


def test_cuda_is_accepted_and_recorded() -> None:
    cfg = config.RunConfig.from_dict(_cnn_config(device="cuda"))
    assert cfg.training["device"] == "cuda"
    assert cfg.as_dict()["training"]["device"] == "cuda"


def test_cpu_default_is_stripped_from_the_config() -> None:
    """Absent by default keeps existing config hashes (replayability)."""
    explicit = config.RunConfig.from_dict(_cnn_config(device="cpu"))
    implicit = config.RunConfig.from_dict(_cnn_config())

    assert "device" not in explicit.training
    assert explicit.config_hash() == implicit.config_hash()


def test_unknown_device_is_rejected() -> None:
    with pytest.raises(config.ConfigError):
        config.RunConfig.from_dict(_cnn_config(device="mps"))


def test_baseline_rejects_device_key() -> None:
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "runs/baseline_live.json").read_text()
    )
    raw["training"]["device"] = "cuda"
    with pytest.raises(config.ConfigError):
        config.RunConfig.from_dict(raw)
