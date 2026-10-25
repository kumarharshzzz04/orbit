from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from support import make_config, write_config

from ml_sandbox import paths
from ml_sandbox.evaluate import METRIC_NAMES


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
    assert len(lines) == 1, f"expected exactly one stdout line, got: {proc.stdout!r}"
    return json.loads(lines[-1])


def test_baseline_run_is_replayable(tmp_path, config_writer) -> None:
    config_path = config_writer(model="baseline", name="baseline-cli")
    first_dir = tmp_path / "run-1"
    second_dir = tmp_path / "run-2"

    first = run_cli("--config", str(config_path), "--out", str(first_dir), "--quiet")
    assert first.returncode == 0, first.stderr
    first_payload = last_json(first)
    assert first_payload["ok"] is True
    assert set(first_payload["metrics"]) == set(METRIC_NAMES)
    for value in first_payload["metrics"].values():
        assert 0.0 <= value <= 1.0

    second = run_cli("--config", str(config_path), "--out", str(second_dir), "--quiet")
    assert second.returncode == 0, second.stderr
    second_payload = last_json(second)
    assert second_payload["ok"] is True

    assert first_payload["config_hash"] == second_payload["config_hash"]
    assert first_payload["dataset_fingerprint"] == second_payload["dataset_fingerprint"]
    assert first_payload["split_fingerprint"] == second_payload["split_fingerprint"]
    for name in METRIC_NAMES:
        assert first_payload["metrics"][name] == pytest.approx(
            second_payload["metrics"][name], abs=1e-12
        ), name

    for filename in (
        "config.json",
        "metrics.json",
        "confusion_matrix.json",
        "model.joblib",
        "model_meta.json",
        "feature_importance.json",
        "predictions.csv",
        "run_record.json",
        "progress.jsonl",
    ):
        assert (first_dir / filename).exists(), filename

    artifact = Path(first_payload["artifact"])
    assert artifact.is_dir()
    assert artifact.name == "run-1"

    record = json.loads((first_dir / "run_record.json").read_text())
    for key in (
        "id",
        "hypothesis_id",
        "config_hash",
        "seed",
        "git_commit",
        "dataset_fingerprint",
        "metrics",
        "artifact_path",
        "verdict",
        "diagnosis",
        "created_at",
        "replayable",
    ):
        assert key in record, key
    assert record["verdict"] == "PENDING"
    assert record["diagnosis"] is None
    assert record["artifact_path"].endswith("/")
    assert isinstance(record["replayable"], bool)
    assert record["id"] == "run-1"
    assert record["seed"] == 42

    with (first_dir / "predictions.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == record["split_sizes"]["test"]
    assert set(rows[0]) == {
        "target_id",
        "host_star",
        "disposition",
        "label",
        "probability",
        "prediction",
        "threshold",
    }

    progress_lines = (first_dir / "progress.jsonl").read_text().splitlines()
    assert any('"stage": "saved"' in line for line in progress_lines)
    assert any('"stage": "train"' in line for line in progress_lines)


def test_invalid_config_fails_with_json(tmp_path) -> None:
    raw = make_config(tmp_path, model="baseline")
    raw["model"] = "not-a-model"
    path = write_config(tmp_path / "bad.json", raw)
    proc = run_cli("--config", str(path), "--out", str(tmp_path / "out"), "--quiet")
    assert proc.returncode != 0
    payload = last_json(proc)
    assert payload["ok"] is False
    assert "model" in payload["error"]


def test_non_empty_output_requires_force(tmp_path, config_writer) -> None:
    config_path = config_writer(model="baseline", name="force-test")
    out_dir = tmp_path / "occupied"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("do not clobber", encoding="utf-8")

    refused = run_cli("--config", str(config_path), "--out", str(out_dir), "--quiet")
    assert refused.returncode != 0
    assert last_json(refused)["ok"] is False
    assert "not empty" in last_json(refused)["error"]
    assert (out_dir / "keep.txt").read_text(encoding="utf-8") == "do not clobber"
    assert not (out_dir / "run_record.json").exists()

    forced = run_cli(
        "--config",
        str(config_path),
        "--out",
        str(out_dir),
        "--force",
        "--quiet",
    )
    assert forced.returncode == 0, forced.stderr
    assert last_json(forced)["ok"] is True


def test_single_class_cache_is_rejected(tmp_path) -> None:
    raw = make_config(tmp_path / "missing", data={"stub_targets": 140})
    path = write_config(tmp_path / "missing.json", raw)
    proc = run_cli("--config", str(path), "--out", str(tmp_path / "out"), "--quiet")
    assert proc.returncode != 0
    assert last_json(proc)["ok"] is False
