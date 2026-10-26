"""orbit-hist-v1: histogram gradient boosting on the engineered feature set.

One change against `orbit-baseline-v1`: the estimator family. The champion uses
`GradientBoostingClassifier`, which requires imputation and builds trees on
sorted feature values. `HistGradientBoostingClassifier` bins the features
(handles NaN natively, so no imputer), supports L2 regularisation, and was the
only candidate in `ml_sandbox.model_search` whose paired 95% interval against
the champion excluded zero on the train+val pool.

Everything else is untouched on purpose: same 12 catalog features, same seed,
same validation-F1 threshold rule, same evaluation harness, same registry row
contract. The one-change rule is what makes the comparison mean anything.
"""

from __future__ import annotations

import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

from ..config import RunConfig
from ..dataset import DatasetSplit
from .base import ModelResult


def _sample_weights(labels: np.ndarray, class_weight: object) -> np.ndarray | None:
    if class_weight is None:
        return None
    if class_weight == "balanced":
        return compute_sample_weight("balanced", labels)
    return np.where(labels == 1, float(class_weight), 1.0)


def build_estimator(cfg: RunConfig) -> Pipeline:
    params = dict(cfg.model_params)
    params.pop("class_weight", None)
    estimator = HistGradientBoostingClassifier(**params, random_state=cfg.seed)
    # No imputer: HistGradientBoosting consumes NaN directly.
    return Pipeline([("model", estimator)])


def fit_predict(
    train: DatasetSplit,
    validation: DatasetSplit,
    test: DatasetSplit,
    *,
    cfg: RunConfig,
    out_dir: str | Path,
) -> ModelResult:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    pipeline = build_estimator(cfg)
    weights = _sample_weights(train.labels, cfg.model_params.get("class_weight"))
    fit_kwargs = {"model__sample_weight": weights} if weights is not None else {}
    pipeline.fit(train.feature_matrix, train.labels, **fit_kwargs)
    seconds = time.perf_counter() - started

    train_probabilities = pipeline.predict_proba(train.feature_matrix)[:, 1]
    val_probabilities = pipeline.predict_proba(validation.feature_matrix)[:, 1]
    test_probabilities = pipeline.predict_proba(test.feature_matrix)[:, 1]

    artifact_file = "model.joblib"
    joblib.dump(pipeline, out_path / artifact_file, compress=0)

    return ModelResult(
        val_probabilities=np.asarray(val_probabilities, dtype=np.float64),
        test_probabilities=np.asarray(test_probabilities, dtype=np.float64),
        train_probabilities=np.asarray(train_probabilities, dtype=np.float64),
        artifact_file=artifact_file,
        training={
            "model_family": "hist",
            "train_seconds": round(seconds, 4),
            "n_features": int(train.feature_matrix.shape[1]),
            "feature_set": cfg.feature_set,
            "class_weight": cfg.model_params.get("class_weight"),
            "params": {
                key: value
                for key, value in cfg.model_params.items()
                if key != "class_weight"
            },
            "feature_importance_note": (
                "HistGradientBoosting exposes no feature_importances_; use "
                "permutation importance on the validation split if the dashboard "
                "needs drivers."
            ),
        },
    )
