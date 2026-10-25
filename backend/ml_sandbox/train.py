"""Train and evaluate one model: ``python -m ml_sandbox.train``.

Contract (AGENTS.md 3.3):
- exit 0 on success, non-zero on any failure
- the LAST stdout line is always one JSON object
- progress goes to stderr as ``ORBIT_PROGRESS {json}`` and to ``progress.jsonl``
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from . import dataset, evaluate, paths
from .config import load_config

LOG = logging.getLogger("orbit.ml")


class RunError(RuntimeError):
    """Raised when a run cannot proceed (bad cache, empty split, ...)."""


class ProgressWriter:
    """Stream machine-readable progress without polluting stdout."""

    def __init__(self, path: Path) -> None:
        self._handle = path.open("a", encoding="utf-8")

    def emit(self, stage: str, **fields: Any) -> None:
        payload = {"stage": stage, **fields}
        line = json.dumps(payload, sort_keys=True, default=str)
        print(f"ORBIT_PROGRESS {line}", file=sys.stderr, flush=True)
        self._handle.write(line + "\n")
        self._handle.flush()

    def percent(self, stage: str, done: int, total: int, **fields: Any) -> None:
        percent = 100.0 * done / max(total, 1)
        self.emit(
            stage,
            done=int(done),
            total=int(total),
            percent=round(percent, 1),
            **fields,
        )

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> ProgressWriter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _git_info() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=paths.REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if commit.returncode != 0:
            return "unknown", False
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=paths.REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return commit.stdout.strip(), bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return "unknown", False


def _prepare_out_dir(out_dir: str | Path, *, force: bool) -> Path:
    destination = Path(out_dir).expanduser()
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).resolve()
    if destination.exists() and any(destination.iterdir()) and not force:
        raise RunError(
            f"output directory is not empty: {destination}. "
            "Use a new run directory, or --force to overwrite."
        )
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _validate_splits(data: dataset.OrbitDataset) -> dict[str, int]:
    sizes = data.split_sizes
    for name in ("train", "val", "test"):
        if sizes[name] < 3:
            raise RunError(
                f"split {name!r} has only {sizes[name]} targets; "
                "cache more data or use a coarser split"
            )
    if sizes["train"] < 10:
        raise RunError("training split is too small (<10)")
    train_labels = data.labels[data.indices_for_split("train")]
    if np.unique(train_labels).size < 2:
        raise RunError("training split contains a single class")
    return sizes


def _write_predictions(
    path: Path,
    split: dataset.DatasetSplit,
    probabilities: np.ndarray,
    threshold: float,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "target_id",
                "host_star",
                "disposition",
                "label",
                "probability",
                "prediction",
                "threshold",
            ]
        )
        for index, target_id in enumerate(split.target_ids):
            probability = float(probabilities[index])
            writer.writerow(
                [
                    target_id,
                    split.hosts[index],
                    split.dispositions[index],
                    int(split.labels[index]),
                    f"{probability:.6f}",
                    int(probability >= threshold),
                    f"{threshold:.6f}",
                ]
            )


def _run_dir_name(out_dir: Path) -> str:
    return out_dir.name or "run"


def run(
    config_path: str | Path,
    out_dir: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Execute one reproducible training run and return the CLI summary."""
    started = time.perf_counter()
    cfg = load_config(config_path)
    config_hash = cfg.config_hash()
    destination = _prepare_out_dir(out_dir, force=force)
    artifact_rel = paths.relpath(destination).rstrip("/") + "/"

    dataset.write_json(destination / "config.json", cfg.as_dict())

    with ProgressWriter(destination / "progress.jsonl") as progress:
        progress.emit(
            "load",
            config=cfg.name,
            config_hash=config_hash,
            mode=cfg.mode,
            model=cfg.model,
        )
        load_started = time.perf_counter()
        data = dataset.load_dataset(cfg)
        if cfg.mode == "stub" and len(data.target_ids) != cfg.stub_targets:
            raise RunError(
                f"config expects {cfg.stub_targets} stub targets, cache has "
                f"{len(data.target_ids)}. Rebuild the cache or fix data.stub_targets."
            )
        sizes = _validate_splits(data)
        LOG.info(
            "loaded %d targets (train=%d val=%d test=%d) in %.2fs",
            len(data.target_ids),
            sizes["train"],
            sizes["val"],
            sizes["test"],
            time.perf_counter() - load_started,
        )
        LOG.info("dataset fingerprint %s", data.dataset_fingerprint)
        progress.emit(
            "loaded",
            dataset_fingerprint=data.dataset_fingerprint,
            split_fingerprint=data.split_fingerprint,
            split_version=cfg.split_version,
            n_targets=len(data.target_ids),
            **{f"n_{name}": sizes[name] for name in sizes},
        )

        train_split = data.select("train")
        val_split = data.select("val")
        test_split = data.select("test")

        n_inputs = len(data.feature_names) if cfg.model == "baseline" else data.n_bins
        progress.emit(
            "train",
            status="start",
            model=cfg.model,
            n_train=train_split.size,
            n_inputs=n_inputs,
        )
        if cfg.model == "baseline":
            from .models.baseline import fit_predict
        else:
            from .models.cnn import fit_predict

        result = fit_predict(
            train_split,
            val_split,
            test_split,
            cfg=cfg,
            out_dir=destination,
        )
        progress.emit(
            "train",
            status="done",
            seconds=result.training.get("train_seconds"),
            model=cfg.model,
        )

        if cfg.training["threshold_selection"] == "val_f1":
            choice = evaluate.choose_threshold_for(val_split, result.val_probabilities)
            threshold = choice.threshold
            threshold_source = "val_f1"
            threshold_detail: dict[str, Any] = {
                "val_f1": choice.val_f1,
                "n_rows": choice.n_rows,
                "single_class": choice.single_class,
            }
        else:
            threshold = float(cfg.training["threshold"])
            threshold_source = "fixed"
            threshold_detail = {}

        val_eval = evaluate.evaluate_split(
            val_split,
            result.val_probabilities,
            threshold=threshold,
            threshold_source=threshold_source,
        )
        test_eval = evaluate.evaluate_split(
            test_split,
            result.test_probabilities,
            threshold=threshold,
            threshold_source=threshold_source,
        )
        train_eval = evaluate.evaluate_split(
            train_split,
            result.train_probabilities,
            threshold=threshold,
            threshold_source=threshold_source,
        )
        if test_eval.single_class_primary:
            LOG.warning(
                "test primary truth has a single class; ROC-AUC is reported as 0.5"
            )

        _write_predictions(
            destination / "predictions.csv",
            test_split,
            result.test_probabilities,
            threshold,
        )

        metrics_detail = {
            **test_eval.detail(),
            "threshold_selection": cfg.training["threshold_selection"],
            "threshold_choice": threshold_detail,
            "validation": {
                "metrics": val_eval.metrics,
                **val_eval.detail(),
            },
            "train": {
                "metrics": train_eval.metrics,
                "n": train_eval.n_all,
            },
            "split_sizes": sizes,
        }
        dataset.write_json(
            destination / "metrics.json",
            {
                "run_id": _run_dir_name(destination),
                "model": cfg.name,
                "model_family": cfg.model,
                "config_hash": config_hash,
                "dataset_fingerprint": data.dataset_fingerprint,
                "split_fingerprint": data.split_fingerprint,
                "metrics": test_eval.metrics,
                "candidate_inclusive_metrics": test_eval.candidate_inclusive,
                "confusion_matrix": test_eval.confusion,
                "metrics_detail": metrics_detail,
            },
        )
        dataset.write_json(
            destination / "confusion_matrix.json",
            {
                "threshold": threshold,
                "primary": test_eval.confusion["primary"],
                "candidate_inclusive": test_eval.confusion["candidate_inclusive"],
            },
        )
        dataset.write_json(
            destination / "model_meta.json",
            {
                "artifact_file": result.artifact_file,
                "model": cfg.name,
                "model_family": cfg.model,
                "feature_set": cfg.feature_set,
                "feature_names": data.feature_names,
                "n_bins": data.n_bins,
                "threshold": threshold,
                "threshold_source": threshold_source,
                "input": result.training.get("input", "engineered features"),
                "config_hash": config_hash,
                "dataset_fingerprint": data.dataset_fingerprint,
                "seed": cfg.seed,
            },
        )

        commit, dirty = _git_info()
        replayable = bool(
            commit != "unknown"
            and not dirty
            and data.dataset_fingerprint
            and data.split_fingerprint
            and config_hash
        )
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        duration = round(time.perf_counter() - started, 3)
        run_record = {
            "id": _run_dir_name(destination),
            "hypothesis_id": cfg.hypothesis_id,
            "config_hash": config_hash,
            "seed": cfg.seed,
            "git_commit": commit,
            "git_dirty": dirty,
            "dataset_fingerprint": data.dataset_fingerprint,
            "split_fingerprint": data.split_fingerprint,
            "split_version": cfg.split_version,
            "metrics": test_eval.metrics,
            "artifact_path": artifact_rel,
            "verdict": "PENDING",
            "diagnosis": None,
            "created_at": created_at,
            "model": cfg.name,
            "model_family": cfg.model,
            "feature_set": cfg.feature_set,
            "replayable": replayable,
            "threshold": threshold,
            "threshold_source": threshold_source,
            "candidate_inclusive_metrics": test_eval.candidate_inclusive,
            "metrics_detail": metrics_detail,
            "training": result.training,
            "split_sizes": sizes,
            "duration_seconds": duration,
            "config": cfg.as_dict(),
        }
        dataset.write_json(destination / "run_record.json", run_record)

        progress.emit(
            "saved",
            artifact=artifact_rel,
            replayable=replayable,
            seconds=duration,
        )

    summary = {
        "ok": True,
        "run_id": _run_dir_name(destination),
        "metrics": test_eval.metrics,
        "candidate_inclusive_metrics": test_eval.candidate_inclusive,
        "artifact": artifact_rel,
        "config_hash": config_hash,
        "dataset_fingerprint": data.dataset_fingerprint,
        "split_fingerprint": data.split_fingerprint,
        "replayable": replayable,
        "model": cfg.model,
        "threshold": threshold,
        "duration_seconds": duration,
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ml_sandbox.train",
        description="Train and evaluate one ORBIT model on the frozen split.",
    )
    parser.add_argument("--config", required=True, help="path to a run config JSON")
    parser.add_argument("--out", required=True, help="artifact directory for this run")
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow writing into a non-empty output directory (rewrites artifacts)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress human-readable logs on stderr",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.quiet:
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stderr,
            format="%(asctime)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
    try:
        summary = run(args.config, args.out, force=args.force)
    except Exception as exc:  # noqa: BLE001 - contract requires any error as JSON
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                sort_keys=True,
            ),
            flush=True,
        )
        return 1
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
