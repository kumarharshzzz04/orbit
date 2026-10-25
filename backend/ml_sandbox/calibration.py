"""Probability calibration fitted on the validation split.

Motivation (measured, see docs/ML.md): the champion's decision threshold is chosen
on ~45 validation rows and then applied to a test split drawn from a different
region of the data. Cross-validation showed that this transfer is where most of
the F1 loss lives, so a challenger may fit a map from raw scores to calibrated
probabilities on validation and then decide at 0.5.

Platt scaling (a one-dimensional logistic fit on the logit of the raw score) is
used instead of isotonic regression on purpose: isotonic is piecewise constant and
introduces ties, which can lower ROC-AUC and trip the gate's "AUC not degraded"
check. Platt is strictly monotone, so ranking - and therefore AUC - is preserved
exactly and only the threshold moves.

Fitted on validation rows only; no test row is ever seen.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


class CalibrationError(RuntimeError):
    pass


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


def apply_platt(
    val_labels: np.ndarray,
    probabilities: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Fit on ``val`` and map every split through the same calibrator.

    Returns the calibrated arrays and a small dict for the run artifact. If the
    validation split has a single class the fit is undefined, so the raw
    probabilities are returned unchanged and ``applied`` is False.
    """
    labels = np.asarray(val_labels, dtype=np.int64).ravel()
    if "val" not in probabilities:
        raise CalibrationError("probabilities must include a 'val' entry")
    if np.unique(labels).size < 2:
        return dict(probabilities), {
            "method": "platt",
            "applied": False,
            "reason": "validation split has a single class",
        }

    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    model.fit(_logit(probabilities["val"]), labels)

    mapped = {
        name: model.predict_proba(_logit(values))[:, 1]
        for name, values in probabilities.items()
    }
    return mapped, {
        "method": "platt",
        "applied": True,
        "n_val": int(labels.size),
        "n_positive_val": int(labels.sum()),
        "slope": float(model.coef_[0][0]),
        "intercept": float(model.intercept_[0]),
    }
