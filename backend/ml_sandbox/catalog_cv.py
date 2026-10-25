"""Scale check: host-grouped CV on the full KOI catalog, catalog features only.

This answers "is 300 light curves a small dataset?" without downloading anything:
the same 12 catalog features are trained on every usable KOI row, grouped by host
star so no star appears in both train and test, and each fold picks its decision
threshold on an inner validation split rather than on the test fold.

The result is written to JSON so the number in the README and docs/ML.md has a
file behind it. It is deliberately separate from the frozen-split gate: this is a
scale and generalization estimate, not a promotion decision.

Usage:
    python -m ml_sandbox.catalog_cv --out ../runs/evidence/catalog_full_cv.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from . import evaluate, features, labels, paths
from .models import baseline

SEED = 42
N_FOLDS = 5
INNER_VAL_FRACTION = 0.2


class CatalogCVError(RuntimeError):
    """Raised when the catalog scale check cannot run."""


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=paths.REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_catalog_features(
    csv_path: Path,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Load labels and build the 12-feature matrix for every usable KOI row."""
    if not csv_path.exists():
        raise CatalogCVError(
            f"missing {csv_path}; run `python -m ml_sandbox.build_cache --mode live` "
            "once, or point --koi-csv at a cached KOI table"
        )
    frame = labels.load_koi_labels(csv_path)
    rows = frame.to_dict("records")
    matrix = np.vstack([features.build_feature_vector(row, {}) for row in rows]).astype(
        np.float32
    )
    columns = features.indices_for("catalog_v1")

    fingerprint = hashlib.sha1(csv_path.read_bytes()).hexdigest()
    arrays = {
        "target_id": frame["target_id"].to_numpy(),
        "host_star": frame["host_star"].to_numpy(),
        "label": frame["label"].to_numpy(dtype=np.int64),
        "disposition": frame["koi_disposition"].to_numpy(),
        "feature_matrix": matrix[:, columns],
    }
    meta = {
        "koi_csv": paths.relpath(csv_path),
        "koi_csv_sha1": fingerprint,
        "n_targets": int(frame.shape[0]),
        "n_hosts": int(frame["host_star"].nunique()),
        "n_positive": int(frame["label"].sum()),
        "feature_set": "catalog_v1",
        "feature_names": features.FEATURE_SETS["catalog_v1"],
    }
    return arrays, meta


def assign_folds(hosts: np.ndarray, labels_array: np.ndarray) -> np.ndarray:
    """Assign whole hosts to folds, balancing positive counts greedily."""
    rng = np.random.default_rng(SEED)
    unique = np.unique(hosts)
    rng.shuffle(unique)

    host_positive = {}
    for host in unique:
        host_positive[host] = int(labels_array[hosts == host].mean() >= 0.5)

    fold_of: dict[str, int] = {}
    for group in (1, 0):
        counts = np.zeros(N_FOLDS, dtype=int)
        for host in (h for h in unique if host_positive[h] == group):
            target = int(np.argmin(counts))
            fold_of[host] = target
            counts[target] += int(np.sum(hosts == host))
    return np.asarray([fold_of[host] for host in hosts], dtype=int)


def _split_hosts(
    hosts: np.ndarray, mask: np.ndarray, fraction: float
) -> tuple[np.ndarray, np.ndarray]:
    """Split rows inside ``mask`` by host into fit/validation parts."""
    rng = np.random.default_rng(SEED + 1)
    inside = np.unique(hosts[mask])
    rng.shuffle(inside)
    cut = max(int(round(inside.size * (1.0 - fraction))), 1)
    fit_hosts = set(inside[:cut].tolist())
    fit = mask & np.isin(hosts, list(fit_hosts))
    validate = mask & ~fit
    return fit, validate


def _fit_predict(
    matrix: np.ndarray,
    target: np.ndarray,
    fit_mask: np.ndarray,
    predict_mask: np.ndarray,
    cfg,
) -> np.ndarray:
    pipeline = baseline.build_estimator(cfg)
    weights = baseline._sample_weights(
        target[fit_mask], cfg.model_params.get("class_weight")
    )
    kwargs = {"model__sample_weight": weights} if weights is not None else {}
    pipeline.fit(matrix[fit_mask], target[fit_mask], **kwargs)
    return pipeline.predict_proba(matrix[predict_mask])[:, 1]


def run_cv(
    arrays: dict[str, np.ndarray], cfg, folds: int = N_FOLDS
) -> dict[str, object]:
    matrix = arrays["feature_matrix"]
    target = arrays["label"]
    dispositions = arrays["disposition"]
    hosts = arrays["host_star"]
    fold_ids = assign_folds(hosts, target)

    per_fold = []
    oof = np.full(target.size, np.nan)
    oof_threshold = np.full(target.size, np.nan)
    for fold in range(folds):
        test_mask = fold_ids == fold
        train_mask = ~test_mask
        fit_mask, val_mask = _split_hosts(hosts, train_mask, INNER_VAL_FRACTION)

        val_probabilities = _fit_predict(matrix, target, fit_mask, val_mask, cfg)
        mask = evaluate.primary_mask(dispositions[val_mask])
        if not mask.any():
            mask = np.ones(val_mask.sum(), dtype=bool)
        choice = evaluate.select_threshold(
            target[val_mask][mask], val_probabilities[mask]
        )

        probabilities = _fit_predict(matrix, target, train_mask, test_mask, cfg)
        oof[test_mask] = probabilities
        oof_threshold[test_mask] = choice.threshold
        result = evaluate.evaluate_predictions(
            target[test_mask],
            dispositions[test_mask],
            probabilities,
            threshold=choice.threshold,
            threshold_source="inner_val_f1",
        )
        per_fold.append(
            {
                "fold": fold,
                "n_train": int(train_mask.sum()),
                "n_test": result.n_primary,
                "n_positive_test": result.n_positive_primary,
                "threshold": choice.threshold,
                "f1": round(float(result.metrics["f1"]), 4),
                "roc_auc": round(float(result.metrics["roc_auc"]), 4),
                "confusion": result.confusion["primary"],
            }
        )
        print(
            f"fold {fold}: n_train={int(train_mask.sum())} "
            f"n_test={result.n_primary} F1={result.metrics['f1']:.4f} "
            f"AUC={result.metrics['roc_auc']:.4f} threshold={choice.threshold:.2f}",
            file=sys.stderr,
        )

    f1s = np.asarray([row["f1"] for row in per_fold])
    aucs = np.asarray([row["roc_auc"] for row in per_fold])

    # Pooled out-of-fold score, each row judged at its own fold's threshold.
    primary = evaluate.primary_mask(dispositions)
    predicted = (oof[primary] >= oof_threshold[primary]).astype(np.int64)
    truth = target[primary]
    tp = int(np.sum((predicted == 1) & (truth == 1)))
    tn = int(np.sum((predicted == 0) & (truth == 0)))
    fp = int(np.sum((predicted == 1) & (truth == 0)))
    fn = int(np.sum((predicted == 0) & (truth == 1)))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    pooled_f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    )
    return {
        "folds": per_fold,
        "fold_f1_mean": round(float(f1s.mean()), 4),
        "fold_f1_sd": round(float(f1s.std(ddof=1)), 4),
        "fold_auc_mean": round(float(aucs.mean()), 4),
        "fold_auc_sd": round(float(aucs.std(ddof=1)), 4),
        "pooled_oof": {
            "n": int(truth.size),
            "n_positive": int(truth.sum()),
            "f1": round(float(pooled_f1), 4),
            "auc": round(float(roc_auc_score(truth, oof[primary])), 4),
            "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        },
        "oof_probability": [round(float(p), 6) for p in oof],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--koi-csv",
        default=str(paths.mode_root("live") / "koi.csv"),
        help="cached KOI cumulative table (default: data/live/koi.csv)",
    )
    parser.add_argument(
        "--config",
        default=str(paths.REPO_ROOT / "runs" / "baseline_live.json"),
        help="run config whose model hyperparameters and seed are reused",
    )
    parser.add_argument(
        "--out",
        default=str(paths.REPO_ROOT / "runs" / "evidence" / "catalog_full_cv.json"),
        help="where to write the JSON report",
    )
    args = parser.parse_args(argv)

    from . import config as config_module

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = config_module.RunConfig.from_dict(raw)

    arrays, meta = load_catalog_features(Path(args.koi_csv))
    print(
        f"{meta['n_targets']} KOIs, {meta['n_hosts']} host stars, "
        f"{meta['n_positive']} positives, catalog_v1 features",
        file=sys.stderr,
    )
    report = {
        **meta,
        "seed": SEED,
        "n_folds": N_FOLDS,
        "inner_val_fraction": INNER_VAL_FRACTION,
        "threshold_source": "inner validation split of each fold",
        "git_commit": _git_commit(),
        "config": {
            "model_params": cfg.model_params,
            "feature_set": cfg.feature_set,
        },
        **run_cv(arrays, cfg),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"5-fold F1 {report['fold_f1_mean']:.4f} +/- {report['fold_f1_sd']:.4f}  "
        f"AUC {report['fold_auc_mean']:.4f} +/- {report['fold_auc_sd']:.4f}"
    )
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
