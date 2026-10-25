from __future__ import annotations

import json
import os
import subprocess
import sys

from ml_sandbox import paths


def run_build(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("DATA_MODE", None)
    env["PYTHONPATH"] = str(paths.BACKEND_DIR)
    return subprocess.run(
        [sys.executable, "-m", "ml_sandbox.build_cache", *args],
        cwd=paths.BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def last_json(proc: subprocess.CompletedProcess[str]) -> dict:
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, proc.stdout
    return json.loads(lines[-1])


def test_stub_build_cli_contract_and_resume(tmp_path) -> None:
    root = tmp_path / "data"
    first = run_build(
        "--mode",
        "stub",
        "--targets",
        "20",
        "--root",
        str(root),
        "--quiet",
    )
    assert first.returncode == 0, first.stderr
    payload = last_json(first)
    assert payload["ok"] is True
    assert payload["new"] == 20
    assert payload["processed"] == 20
    assert len(payload["dataset_fingerprint"]) == 40
    assert (root / "cache" / "manifest.json").exists()
    assert (root / "koi.csv").exists()
    assert (root / "cache_build.json").exists()

    second = run_build(
        "--mode",
        "stub",
        "--targets",
        "20",
        "--root",
        str(root),
        "--quiet",
    )
    assert second.returncode == 0, second.stderr
    resumed = last_json(second)
    assert resumed["reused"] == 20
    assert resumed["new"] == 0
    assert resumed["dataset_fingerprint"] == payload["dataset_fingerprint"]


def test_build_cli_requires_enough_targets(tmp_path) -> None:
    proc = run_build(
        "--mode",
        "stub",
        "--targets",
        "3",
        "--root",
        str(tmp_path / "data"),
        "--quiet",
    )
    assert proc.returncode == 2
    assert last_json(proc)["ok"] is False
