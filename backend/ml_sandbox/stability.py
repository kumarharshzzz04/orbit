"""Grouped bootstrap confidence intervals for a scored test split.

32 primary test targets is small: one flipped target moves F1 by ~0.03. A point
estimate alone invites over-reading, so every reported live number can be
accompanied by a 95% interval that resamples whole host stars (the split unit).

    python -m ml_sandbox.stability --predictions artifacts/baseline_live/predictions.csv

Prints a short table, then one JSON line as the last line (same CLI convention as
`train`)::

    {"ok": true, "n": 32, "metrics": {...}, "ci": {"f1": [lo, hi], ...}}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from . import evaluate

DEFAULT_N_BOOT = 2000
DEFAULT_ALPHA = 0.05


def load_predictions(path: str | Path) -> dict[str, np.ndarray]:
    """Read a run's ``predictions.csv`` into arrays with the primary mask."""
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"no predictions in {path}")
    dispositions = np.asarray([r["disposition"] for r in rows], dtype=object)
    return {
        "labels": np.asarray([int(r["label"]) for r in rows], dtype=np.int64),
        "probabilities": np.asarray(
            [float(r["probability"]) for r in rows], dtype=np.float64
        ),
        "groups": np.asarray([r["host_star"] for r in rows], dtype=object),
        "threshold": np.asarray(
            [float(r["threshold"]) for r in rows], dtype=np.float64
        ),
        "primary": evaluate.primary_mask(dispositions),
        "target_ids": np.asarray([r["target_id"] for r in rows], dtype=object),
    }


def _point(labels, probabilities, threshold) -> tuple[dict, dict]:
    metrics, confusion, _ = evaluate._binary_metrics(  # noqa: SLF001 - same package
        labels, probabilities, threshold
    )
    return metrics, confusion


def bootstrap_ci(
    labels: np.ndarray,
    probabilities: np.ndarray,
    groups: np.ndarray,
    threshold: float,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = 42,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, object]:
    """Percentile CI from resampling host stars, not individual rows.

    Resampling rows would pretend targets sharing a star are independent; they
    are not, which is why the split is grouped in the first place.
    """
    labels = np.asarray(labels, dtype=np.int64).ravel()
    probabilities = np.asarray(probabilities, dtype=np.float64).ravel()
    groups = np.asarray(groups, dtype=object).ravel()
    if not (labels.size == probabilities.size == groups.size):
        raise ValueError("labels, probabilities and groups must align")

    unique = np.unique(groups)
    if unique.size < 2:
        raise ValueError("need at least two host groups to bootstrap")
    index_by_group = {group: np.flatnonzero(groups == group) for group in unique}

    rng = np.random.default_rng(seed)
    f1_values: list[float] = []
    auc_values: list[float] = []
    skipped_auc = 0
    for _ in range(int(n_boot)):
        picked = rng.choice(unique, size=unique.size, replace=True)
        index = np.concatenate([index_by_group[group] for group in picked])
        metrics, _, auc_defined = evaluate._binary_metrics(  # noqa: SLF001
            labels[index], probabilities[index], threshold
        )
        f1_values.append(metrics["f1"])
        if auc_defined:
            auc_values.append(metrics["roc_auc"])
        else:
            skipped_auc += 1

    lower = 100 * (alpha / 2)
    upper = 100 * (1 - alpha / 2)
    auc_ci = (
        [
            float(np.percentile(auc_values, lower)),
            float(np.percentile(auc_values, upper)),
        ]
        if auc_values
        else [float("nan"), float("nan")]
    )
    return {
        "n_boot": int(n_boot),
        "n_groups": int(unique.size),
        "alpha": float(alpha),
        "seed": int(seed),
        "skipped_auc_samples": int(skipped_auc),
        "ci": {
            "f1": [
                float(np.percentile(f1_values, lower)),
                float(np.percentile(f1_values, upper)),
            ],
            "roc_auc": auc_ci,
        },
    }


def summarize(
    path: str | Path, *, n_boot: int = DEFAULT_N_BOOT, seed: int = 42
) -> dict:
    data = load_predictions(path)
    mask = data["primary"]
    labels = data["labels"][mask]
    probabilities = data["probabilities"][mask]
    groups = data["groups"][mask]
    threshold = float(data["threshold"][0]) if data["threshold"].size else 0.5

    metrics, confusion = _point(labels, probabilities, threshold)
    result = bootstrap_ci(
        labels, probabilities, groups, threshold, n_boot=n_boot, seed=seed
    )
    return {
        "ok": True,
        "predictions": str(path),
        "n": int(labels.size),
        "n_positive": int(labels.sum()),
        "n_groups": int(result["n_groups"]),
        "threshold": threshold,
        "metrics": metrics,
        "confusion": confusion,
        "bootstrap": result,
        "ci": result["ci"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, help="path to predictions.csv")
    parser.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = summarize(args.predictions, n_boot=args.n_boot, seed=args.seed)
    except Exception as exc:  # noqa: BLE001 - CLI contract: JSON last, non-zero exit
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 1
    metrics = summary["metrics"]
    ci = summary["ci"]
    print(
        f"{Path(args.predictions).parent.name}: "
        f"F1 {metrics['f1']:.4f} [{ci['f1'][0]:.4f}, {ci['f1'][1]:.4f}]  "
        f"AUC {metrics['roc_auc']:.4f} "
        f"[{ci['roc_auc'][0]:.4f}, {ci['roc_auc'][1]:.4f}]  "
        f"n={summary['n']} pos={summary['n_positive']} hosts={summary['n_groups']}",
        file=sys.stderr,
    )
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
