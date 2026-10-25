from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from ml_sandbox import stability


def _write_predictions(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(target: str, host: str, disposition: str, label: int, prob: float) -> dict:
    return {
        "target_id": target,
        "host_star": host,
        "disposition": disposition,
        "label": label,
        "probability": prob,
        "prediction": int(prob >= 0.5),
        "threshold": 0.5,
    }


def test_separable_split_has_high_lower_bound() -> None:
    labels = np.array([1] * 20 + [0] * 20)
    probabilities = np.array([0.9] * 20 + [0.1] * 20)
    groups = np.array([f"h{i}" for i in range(40)])

    result = stability.bootstrap_ci(labels, probabilities, groups, 0.5, n_boot=300)

    assert result["ci"]["f1"][0] == 1.0
    assert result["ci"]["f1"][1] == 1.0
    assert result["n_groups"] == 40


def test_bootstrap_is_deterministic_and_resamples_hosts() -> None:
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 2, size=60)
    probabilities = np.clip(labels * 0.5 + rng.normal(0.25, 0.2, size=60), 0.0, 1.0)
    # Two rows per host: a row-level resample would overstate precision.
    groups = np.array([f"h{i // 2}" for i in range(60)])

    first = stability.bootstrap_ci(labels, probabilities, groups, 0.5, n_boot=200)
    second = stability.bootstrap_ci(labels, probabilities, groups, 0.5, n_boot=200)

    assert first == second
    assert first["n_groups"] == 30
    assert first["ci"]["f1"][0] <= first["ci"]["f1"][1]


def test_primary_mask_drops_candidates(tmp_path: Path) -> None:
    path = _write_predictions(
        tmp_path / "predictions.csv",
        [
            _row("K1.01", "1", "CONFIRMED", 1, 0.9),
            _row("K2.01", "2", "CANDIDATE", 1, 0.9),
            _row("K3.01", "3", "FALSE POSITIVE", 0, 0.1),
        ],
    )

    data = stability.load_predictions(path)

    assert data["primary"].tolist() == [True, False, True]


def test_cli_prints_one_json_line(tmp_path: Path, capsys) -> None:
    path = _write_predictions(
        tmp_path / "predictions.csv",
        [
            _row("K1.01", "1", "CONFIRMED", 1, 0.9),
            _row("K2.01", "2", "FALSE POSITIVE", 0, 0.1),
        ],
    )

    assert stability.main(["--predictions", str(path), "--n-boot", "50"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["n"] == 2
    assert payload["metrics"]["f1"] == 1.0


def test_cli_reports_failure_as_json(tmp_path: Path, capsys) -> None:
    assert stability.main(["--predictions", str(tmp_path / "missing.csv")]) == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert "FileNotFoundError" in payload["error"]
