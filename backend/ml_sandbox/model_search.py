"""Host-grouped model search on the live cache, without touching the test split.

Why this exists
---------------
The champion's hyperparameters were chosen by hand in the first hour of the
sprint and never compared against alternatives or other model families. This
module runs a small, declared grid over the **train + val** rows only and
reports paired per-fold differences against the champion, so a change is
adopted only when the gain stands outside fold noise.

The frozen test split is excluded by construction: a model chosen on rows that
include test rows would make the final score meaningless. Selection happens on
759 rows (split v2 train 625 + val 134); the 134 test rows are scored once,
afterwards, by the normal `ml_sandbox.train` path.

Usage
-----
    python -m ml_sandbox.model_search --config runs/baseline_live.json
    python -m ml_sandbox.model_search --config runs/baseline_live.json --quick
    python -m ml_sandbox.model_search --config runs/baseline_live.json --families gbm,hist

Writes `runs/evidence/model_search_v2.json` (dataset + split fingerprints, the
grid, per-fold numbers, and a paired decision against the champion).
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from typing import Any

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from . import dataset, evaluate, paths
from .config import load_config
from .models import baseline

FOLDS = 5
INNER_VAL_FRACTION = 0.25
DEFAULT_SEED = 42

# Declared before the search runs. Small on purpose: 759 rows cannot support a
# wide grid without the winner being noise.
GRIDS: dict[str, dict[str, list[Any]]] = {
    "gbm": {
        "max_depth": [6, 8],
        "min_samples_leaf": [4, 8],
        "class_weight": [None, "balanced"],
    },
    "hist": {
        "max_leaf_nodes": [15, 31],
        "min_samples_leaf": [10, 20],
        "l2_regularization": [0.0, 1.0],
        "class_weight": [None, "balanced"],
    },
    "rf": {
        "max_depth": [None, 12],
        "min_samples_leaf": [1, 2],
        "class_weight": [None, "balanced"],
    },
    "et": {
        "max_depth": [None, 12],
        "min_samples_leaf": [1, 2],
        "class_weight": [None, "balanced"],
    },
}
FIXED = {
    "gbm": {"learning_rate": 0.05, "n_estimators": 300, "subsample": 0.9},
    "hist": {"learning_rate": 0.05, "max_iter": 400},
    "rf": {"n_estimators": 400, "n_jobs": 1},
    "et": {"n_estimators": 400, "n_jobs": 1},
}


def build(family: str, params: dict[str, Any], seed: int) -> Pipeline:
    """Estimator for one candidate. Imputation stays inside the pipeline."""
    settings = {**FIXED[family], **params}
    weight = settings.pop("class_weight", None)
    del weight  # applied as sample_weight at fit time, never a ctor argument

    if family == "gbm":
        model = GradientBoostingClassifier(**settings, random_state=seed)
        return Pipeline(
            [("impute", SimpleImputer(strategy="median")), ("model", model)]
        )
    if family == "hist":
        model = HistGradientBoostingClassifier(**settings, random_state=seed)
        # HistGradientBoosting handles NaN natively; no imputer needed.
        return Pipeline([("model", model)])
    if family == "rf":
        model = RandomForestClassifier(**settings, random_state=seed)
        return Pipeline(
            [("impute", SimpleImputer(strategy="median")), ("model", model)]
        )
    if family == "et":
        model = ExtraTreesClassifier(**settings, random_state=seed)
        return Pipeline(
            [("impute", SimpleImputer(strategy="median")), ("model", model)]
        )
    raise ValueError(f"unknown model family {family!r}")


def assign_folds(
    hosts: np.ndarray, labels: np.ndarray, seed: int = DEFAULT_SEED
) -> np.ndarray:
    """Whole hosts to folds, greedily balancing positive counts (no leakage)."""
    rng = np.random.default_rng(seed)
    unique = np.unique(hosts)
    rng.shuffle(unique)

    host_label = {host: int(labels[hosts == host].mean() >= 0.5) for host in unique}
    fold_of: dict[str, int] = {}
    for wanted in (1, 0):
        counts = np.zeros(FOLDS, dtype=int)
        for host in unique:
            if host_label[host] != wanted:
                continue
            target = int(np.argmin(counts))
            fold_of[host] = target
            counts[target] += int(np.sum(hosts == host))
    return np.asarray([fold_of[host] for host in hosts], dtype=int)


def inner_val_mask(hosts: np.ndarray, seed: int) -> np.ndarray:
    """Boolean mask picking a host-grouped validation slice."""
    rng = np.random.default_rng(seed)
    unique = np.unique(hosts)
    rng.shuffle(unique)
    n_val = max(1, int(round(unique.size * INNER_VAL_FRACTION)))
    return np.isin(hosts, unique[:n_val])


def _candidates(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(grid)
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(grid[key] for key in keys))
    ]


def run_candidate(
    family: str,
    params: dict[str, Any],
    data: dataset.OrbitDataset,
    fold_ids: np.ndarray,
    pool: np.ndarray,
    seed: int,
) -> dict[str, Any]:
    features = data.feature_matrix[pool]
    labels = data.labels[pool]
    dispositions = data.dispositions[pool]
    hosts = data.hosts[pool]

    folds: list[dict[str, Any]] = []
    for fold in range(FOLDS):
        outer_test = fold_ids == fold
        outer_train = ~outer_test
        train_indices = np.flatnonzero(outer_train)
        inner_val = np.zeros(pool.size, dtype=bool)
        inner_val[train_indices] = inner_val_mask(hosts[outer_train], seed + fold)
        inner_train = outer_train & ~inner_val

        pipeline = build(family, params, seed)
        weight = params.get("class_weight")
        if family in {"gbm", "rf", "et"}:
            weights = baseline._sample_weights(labels[inner_train], weight)
        else:
            weights = baseline._sample_weights(labels[inner_train], weight)
        kwargs = {"model__sample_weight": weights} if weights is not None else {}
        pipeline.fit(features[inner_train], labels[inner_train], **kwargs)

        val_prob = pipeline.predict_proba(features[inner_val])[:, 1]
        choice = evaluate.select_threshold(labels[inner_val], val_prob)
        test_prob = pipeline.predict_proba(features[outer_test])[:, 1]
        result = evaluate.evaluate_predictions(
            labels[outer_test],
            dispositions[outer_test],
            test_prob,
            threshold=choice.threshold,
        )
        folds.append(
            {
                "fold": fold,
                "threshold": float(choice.threshold),
                "n": int(result.n_primary),
                "n_positive": int(result.n_positive_primary),
                "f1": float(result.metrics["f1"]),
                "auc": float(result.metrics["roc_auc"]),
            }
        )

    f1s = np.array([fold["f1"] for fold in folds], dtype=float)
    aucs = np.array([fold["auc"] for fold in folds], dtype=float)
    return {
        "family": family,
        "params": params,
        "folds": folds,
        "f1_mean": float(f1s.mean()),
        "f1_sd": float(f1s.std(ddof=1)),
        "auc_mean": float(aucs.mean()),
        "auc_sd": float(aucs.std(ddof=1)),
    }


def paired_interval(reference: np.ndarray, other: np.ndarray) -> dict[str, Any]:
    """Mean paired difference and its 95% t-interval over folds (4 df, t=2.776)."""
    diff = other - reference
    mean = float(diff.mean())
    sd = float(diff.std(ddof=1))
    half = 2.776 * sd / float(np.sqrt(diff.size)) if sd > 0 else 0.0
    return {
        "mean_diff": mean,
        "sd": sd,
        "ci_low": mean - half,
        "ci_high": mean + half,
        "conclusive": bool(mean - half > 0.0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Host-grouped model search")
    parser.add_argument("--config", default="runs/baseline_live.json")
    parser.add_argument("--out", default="runs/evidence/model_search_v2.json")
    parser.add_argument("--families", default="gbm,hist,rf,et")
    parser.add_argument("--quick", action="store_true", help="champion config only")
    args = parser.parse_args(argv)

    cfg = load_config(paths.resolve(args.config))
    started = time.perf_counter()
    data = dataset.load_dataset(cfg)
    pool = np.flatnonzero(data.split_names != "test")
    excluded = int(data.target_ids.size - pool.size)
    hosts = data.hosts[pool]
    labels = data.labels[pool]
    fold_ids = assign_folds(hosts, labels, cfg.seed)

    champion = {
        "family": "gbm",
        "params": {
            "max_depth": int(cfg.model_params.get("max_depth", 6)),
            "min_samples_leaf": int(cfg.model_params.get("min_samples_leaf", 2)),
            "class_weight": cfg.model_params.get("class_weight"),
        },
    }

    families = (
        ["gbm"] if args.quick else [name.strip() for name in args.families.split(",")]
    )
    candidates: list[dict[str, Any]] = [champion]
    for family in families:
        for params in _candidates(GRIDS[family]):
            candidates.append({"family": family, "params": params})

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = json.dumps(candidate, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result = run_candidate(
            candidate["family"], candidate["params"], data, fold_ids, pool, cfg.seed
        )
        results.append(result)
        print(
            f"{result['family']:5s} {json.dumps(result['params'], sort_keys=True):55s} "
            f"F1 {result['f1_mean']:.4f} +/- {result['f1_sd']:.4f}  AUC {result['auc_mean']:.4f}",
            flush=True,
        )

    reference = np.array([fold["f1"] for fold in results[0]["folds"]], dtype=float)
    for result in results:
        other = np.array([fold["f1"] for fold in result["folds"]], dtype=float)
        result["vs_champion"] = paired_interval(reference, other)

    ranked = sorted(results, key=lambda row: (-row["f1_mean"], -row["auc_mean"]))
    # Adoption requires the paired interval to exclude zero. Best mean alone is
    # not enough: with five folds, a +0.02 point estimate can be pure noise.
    eligible = [row for row in ranked if row["vs_champion"]["conclusive"]]
    winner = eligible[0] if eligible else results[0]
    improved = bool(eligible)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "command": "python -m ml_sandbox.model_search --config " + str(args.config),
        "dataset_fingerprint": data.dataset_fingerprint,
        "split_fingerprint": data.split_fingerprint,
        "split_sizes": data.split_counts,
        "selection_pool": {
            "rows": int(pool.size),
            "hosts": int(np.unique(hosts).size),
            "positives": int(labels.sum()),
            "excluded_test_rows": excluded,
        },
        "folds": FOLDS,
        "inner_val_fraction": INNER_VAL_FRACTION,
        "grids": {name: GRIDS[name] for name in families},
        "fixed": {name: FIXED[name] for name in families},
        "champion": champion,
        "results": results,
        "winner": {"family": winner["family"], "params": winner["params"]},
        "winner_improves_conclusively": improved,
        "decision_rule": (
            "adopt only if the paired 95% interval of per-fold F1 difference "
            "against the champion excludes 0"
        ),
        "seconds": round(time.perf_counter() - started, 1),
    }

    out = paths.resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("")
    for rank, result in enumerate(ranked[:6], start=1):
        diff = result["vs_champion"]
        print(
            f"{rank}. {result['family']:5s} F1 {result['f1_mean']:.4f} +/- {result['f1_sd']:.4f}  "
            f"delta {diff['mean_diff']:+.4f} [{diff['ci_low']:+.4f}, {diff['ci_high']:+.4f}]  "
            f"{json.dumps(result['params'], sort_keys=True)}"
        )
    print(f"winner improves conclusively: {improved}")
    print(f"wrote {out} in {report['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
