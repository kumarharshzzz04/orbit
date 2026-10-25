"""orbit-baseline-v1: gradient boosting on the engineered feature vector.

Deliberately boring and fast. 300 shallow trees clear the tabular bar in
seconds, which leaves the CNN as the interesting challenger and keeps CI cheap.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

from .. import features
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
    estimator = GradientBoostingClassifier(
        **params,
        random_state=cfg.seed,
    )
    return Pipeline(
        steps=[
            (
                "impute",
                SimpleImputer(strategy="median", keep_empty_features=True),
            ),
            ("model", estimator),
        ]
    )


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

    selected_names = features.FEATURE_SETS[cfg.feature_set]
    estimator = pipeline.named_steps["model"]
    importances = getattr(estimator, "feature_importances_", None)
    if importances is not None and len(importances) == len(selected_names):
        ranked = sorted(
            zip(selected_names, importances, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        # Ordered on purpose: the dashboard shows the top drivers first.
        (out_path / "feature_importance.json").write_text(
            json.dumps(
                [
                    {"feature": str(name), "importance": float(value)}
                    for name, value in ranked
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return ModelResult(
        val_probabilities=np.asarray(val_probabilities, dtype=np.float64),
        test_probabilities=np.asarray(test_probabilities, dtype=np.float64),
        train_probabilities=np.asarray(train_probabilities, dtype=np.float64),
        artifact_file=artifact_file,
        training={
            "model_family": "baseline",
            "train_seconds": round(seconds, 4),
            "n_features": int(train.feature_matrix.shape[1]),
            "feature_set": cfg.feature_set,
            "class_weight": cfg.model_params.get("class_weight"),
            "params": {
                key: value
                for key, value in cfg.model_params.items()
                if key != "class_weight"
            },
        },
    )
