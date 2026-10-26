from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

from ml_sandbox import paths
from ml_sandbox.config import ConfigError, RunConfig
from ml_sandbox.model_search import assign_folds, paired_interval


def run_cli(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("DATA_MODE", None)
    env["PYTHONPATH"] = str(paths.BACKEND_DIR)
    return subprocess.run(
        [sys.executable, "-m", "ml_sandbox.train", *args],
        cwd=paths.BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def last_json(proc: subprocess.CompletedProcess[str]) -> dict:
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected one stdout line, got: {proc.stdout!r}"
    return json.loads(lines[-1])


def test_hist_defaults_are_filled_in() -> None:
    cfg = RunConfig.from_dict({"name": "h", "model": "hist"})
    assert cfg.model == "hist"
    assert cfg.model_params["max_iter"] == 400
    assert cfg.model_params["max_leaf_nodes"] == 31
    assert cfg.model_params["l2_regularization"] == 1.0
    assert cfg.training["threshold_selection"] == "val_f1"


def test_hist_rejects_cnn_params() -> None:
    with pytest.raises(ConfigError):
        RunConfig.from_dict(
            {
                "name": "h",
                "model": "hist",
                "model_params": {"channels": [16, 32, 48]},
            }
        )


def test_hist_run_is_replayable(tmp_path, config_writer) -> None:
    config_path = config_writer(model="hist", name="hist-cli")
    first = run_cli(
        "--config", str(config_path), "--out", str(tmp_path / "a"), "--quiet"
    )
    assert first.returncode == 0, first.stderr
    payload = last_json(first)
    assert payload["ok"] is True
    assert payload["model"] == "hist"

    second = run_cli(
        "--config", str(config_path), "--out", str(tmp_path / "b"), "--quiet"
    )
    assert second.returncode == 0, second.stderr
    other = last_json(second)
    assert payload["config_hash"] == other["config_hash"]
    for name, value in payload["metrics"].items():
        assert value == pytest.approx(other["metrics"][name], abs=1e-12)

    record = json.loads((tmp_path / "a" / "run_record.json").read_text())
    assert record["training"]["model_family"] == "hist"
    assert record["verdict"] == "PENDING"


def test_fold_assignment_is_host_pure_and_repeatable() -> None:
    hosts = np.array(["h1", "h1", "h2", "h2", "h3", "h4", "h5", "h6"])
    labels = np.array([1, 1, 0, 0, 1, 0, 1, 0])
    first = assign_folds(hosts, labels, seed=42)
    second = assign_folds(hosts, labels, seed=42)
    assert np.array_equal(first, second)
    for host in np.unique(hosts):
        assert len(np.unique(first[hosts == host])) == 1


def test_paired_interval_flags_only_real_gains() -> None:
    reference = np.array([0.80, 0.81, 0.79, 0.82, 0.80])
    noisy = reference + np.array([0.05, -0.05, 0.05, -0.05, 0.05])
    steady = reference + 0.02

    assert paired_interval(reference, noisy)["conclusive"] is False
    assert paired_interval(reference, steady)["conclusive"] is True
    identical = paired_interval(reference, reference)
    assert identical["mean_diff"] == 0.0
    assert identical["conclusive"] is False
