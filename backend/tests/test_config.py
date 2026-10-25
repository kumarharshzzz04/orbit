from __future__ import annotations

import json

import pytest

from ml_sandbox import paths
from ml_sandbox.config import ConfigError, RunConfig, load_config


def test_defaults_are_filled_in() -> None:
    cfg = RunConfig.from_dict({"name": "x", "model": "baseline"})
    assert cfg.mode == "stub"
    assert cfg.n_bins == 400
    assert cfg.split_version == "v1"
    assert cfg.feature_set == "catalog_v1"
    assert cfg.seed == 42
    assert cfg.model_params["n_estimators"] == 300
    assert cfg.training["threshold_selection"] == "val_f1"


def test_hash_is_order_insensitive_and_sensitive_to_values() -> None:
    first = RunConfig.from_dict(
        {
            "name": "x",
            "model": "baseline",
            "seed": 42,
            "features": {"set": "catalog_v1"},
            "model_params": {"n_estimators": 300},
        }
    )
    second = RunConfig.from_dict(
        {
            "model": "baseline",
            "seed": 42,
            "name": "x",
            "model_params": {"n_estimators": 300},
            "features": {"set": "catalog_v1"},
        }
    )
    assert first.config_hash() == second.config_hash()

    changed = RunConfig.from_dict(
        {
            "name": "x",
            "model": "baseline",
            "seed": 43,
            "features": {"set": "catalog_v1"},
        }
    )
    assert changed.config_hash() != first.config_hash()


def test_data_mode_env_override_changes_effective_hash(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"name": "x", "model": "baseline", "data": {"mode": "stub"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("DATA_MODE", raising=False)
    baseline = load_config(config_path)

    monkeypatch.setenv("DATA_MODE", "live")
    overridden = load_config(config_path)
    assert overridden.mode == "live"
    assert overridden.config_hash() != baseline.config_hash()


@pytest.mark.parametrize(
    "raw",
    [
        {"name": "x", "model": "not-a-model"},
        {"name": "", "model": "baseline"},
        {"name": "x", "model": "baseline", "unknown": 1},
        {"name": "x", "model": "baseline", "seed": True},
        {"name": "x", "model": "baseline", "data": {"n_bins": 4}},
        {"name": "x", "model": "baseline", "data": {"split_version": "../evil"}},
        {"name": "x", "model": "baseline", "features": {"set": "nope"}},
        {
            "name": "x",
            "model": "baseline",
            "model_params": {"not_a_param": 1},
        },
        {
            "name": "x",
            "model": "cnn",
            "model_params": {"channels": [32, 64]},
        },
        {
            "name": "x",
            "model": "cnn",
            "training": {"max_epochs": 0},
        },
    ],
)
def test_invalid_configs_are_rejected(raw: dict) -> None:
    with pytest.raises(ConfigError):
        RunConfig.from_dict(raw)


def test_missing_config_file_raises() -> None:
    with pytest.raises(ConfigError):
        load_config(paths.REPO_ROOT / "runs" / "does-not-exist.json")


def test_all_shipped_run_configs_validate() -> None:
    config_paths = sorted((paths.REPO_ROOT / "runs").glob("*.json"))
    assert config_paths, "no run configs found"
    for path in config_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = RunConfig.from_dict(raw, source=str(path))
        assert cfg.name
        assert cfg.model in {"baseline", "cnn"}
        assert cfg.model_params
        assert cfg.data["stub_targets"] == 1500
