"""The one evaluation harness used by every model.

Primary truth = CONFIRMED vs FALSE POSITIVE. CANDIDATE labels are uncertain, so
they are excluded from the primary metric and reported separately as
``candidate_inclusive``. The decision threshold is chosen on validation only and
then frozen for the test split, so no test label ever influences the gate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score

from .dataset import DatasetSplit

METRIC_NAMES = ("accuracy", "precision", "recall", "f1", "roc_auc")
DEFAULT_THRESHOLD_GRID = tuple(np.round(np.linspace(0.05, 0.95, 91), 4))


@dataclass(frozen=True)
class ThresholdChoice:
    threshold: float
    val_f1: float
    n_rows: int
    single_class: bool


@dataclass(frozen=True)
class EvalResult:
    metrics: dict[str, float]
    candidate_inclusive: dict[str, float]
    confusion: dict[str, dict[str, int]]
    threshold: float
    threshold_source: str
    n_primary: int
    n_all: int
    n_positive_primary: int
    roc_auc_defined: bool
    primary_fallback: bool
    single_class_primary: bool

    def detail(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "threshold_source": self.threshold_source,
            "n_primary": self.n_primary,
            "n_all": self.n_all,
            "n_positive_primary": self.n_positive_primary,
            "roc_auc_defined": self.roc_auc_defined,
            "primary_fallback": self.primary_fallback,
            "single_class_primary": self.single_class_primary,
            "candidate_inclusive": self.candidate_inclusive,
            "confusion": self.confusion,
        }


def _binary_metrics(
    labels: np.ndarray, probabilities: np.ndarray, threshold: float
) -> tuple[dict[str, float], dict[str, int], bool]:
    labels = np.asarray(labels, dtype=np.int64).ravel()
    probabilities = np.clip(
        np.asarray(probabilities, dtype=np.float64).ravel(), 0.0, 1.0
    )
    predictions = (probabilities >= threshold).astype(np.int64)

    tp = int(np.sum((predictions == 1) & (labels == 1)))
    tn = int(np.sum((predictions == 0) & (labels == 0)))
    fp = int(np.sum((predictions == 1) & (labels == 0)))
    fn = int(np.sum((predictions == 0) & (labels == 1)))
    total = max(labels.size, 1)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / total

    auc_defined = bool(np.unique(labels).size == 2)
    roc_auc = float(roc_auc_score(labels, probabilities)) if auc_defined else 0.5

    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc),
    }
    confusion = {"tn": tn, "fp": fp, "fn": fn, "tp": tp}
    return metrics, confusion, auc_defined


def select_threshold(
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    grid: tuple[float, ...] | None = None,
) -> ThresholdChoice:
    """Pick the validation threshold that maximizes F1 (ties go near 0.5)."""
    labels = np.asarray(labels, dtype=np.int64).ravel()
    probabilities = np.clip(
        np.asarray(probabilities, dtype=np.float64).ravel(), 0.0, 1.0
    )
    if labels.size == 0:
        return ThresholdChoice(0.5, 0.0, 0, True)

    thresholds = grid or DEFAULT_THRESHOLD_GRID
    single_class = np.unique(labels).size < 2
    best_threshold = 0.5
    best_f1 = -1.0
    best_distance = float("inf")
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(np.int64)
        tp = int(np.sum((predictions == 1) & (labels == 1)))
        fp = int(np.sum((predictions == 1) & (labels == 0)))
        fn = int(np.sum((predictions == 0) & (labels == 1)))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        distance = abs(float(threshold) - 0.5)
        if f1 > best_f1 + 1e-12 or (
            abs(f1 - best_f1) <= 1e-12 and distance < best_distance - 1e-12
        ):
            best_threshold = float(threshold)
            best_f1 = float(f1)
            best_distance = distance
    return ThresholdChoice(
        threshold=best_threshold,
        val_f1=best_f1,
        n_rows=int(labels.size),
        single_class=bool(single_class),
    )


def primary_mask(dispositions: np.ndarray) -> np.ndarray:
    return np.asarray(dispositions, dtype=object) != "CANDIDATE"


def evaluate_predictions(
    labels: np.ndarray,
    dispositions: np.ndarray,
    probabilities: np.ndarray,
    *,
    threshold: float,
    threshold_source: str = "val_f1",
) -> EvalResult:
    """Score one split with the shared harness."""
    labels = np.asarray(labels, dtype=np.int64).ravel()
    dispositions = np.asarray(dispositions, dtype=object).ravel()
    probabilities = np.clip(
        np.asarray(probabilities, dtype=np.float64).ravel(), 0.0, 1.0
    )
    if not (labels.size == dispositions.size == probabilities.size):
        raise ValueError("labels, dispositions and probabilities must align")

    mask = primary_mask(dispositions)
    fallback = False
    if not mask.any():
        mask = np.ones(labels.size, dtype=bool)
        fallback = True

    primary_labels = labels[mask]
    primary_probs = probabilities[mask]
    metrics, confusion_primary, auc_defined = _binary_metrics(
        primary_labels, primary_probs, threshold
    )
    all_metrics, confusion_all, _ = _binary_metrics(labels, probabilities, threshold)

    return EvalResult(
        metrics=metrics,
        candidate_inclusive=all_metrics,
        confusion={
            "primary": {**confusion_primary, "n": int(primary_labels.size)},
            "candidate_inclusive": {**confusion_all, "n": int(labels.size)},
        },
        threshold=float(threshold),
        threshold_source=threshold_source,
        n_primary=int(primary_labels.size),
        n_all=int(labels.size),
        n_positive_primary=int(np.sum(primary_labels == 1)),
        roc_auc_defined=auc_defined,
        primary_fallback=fallback,
        single_class_primary=bool(np.unique(primary_labels).size < 2),
    )


def evaluate_split(
    split: DatasetSplit,
    probabilities: np.ndarray,
    *,
    threshold: float,
    threshold_source: str = "val_f1",
) -> EvalResult:
    return evaluate_predictions(
        split.labels,
        split.dispositions,
        probabilities,
        threshold=threshold,
        threshold_source=threshold_source,
    )


def choose_threshold_for(
    split: DatasetSplit, probabilities: np.ndarray
) -> ThresholdChoice:
    """Choose on validation, using the primary truth (confirmed vs FP)."""
    mask = primary_mask(split.dispositions)
    if not mask.any():
        mask = np.ones(split.labels.size, dtype=bool)
    return select_threshold(split.labels[mask], np.asarray(probabilities)[mask])
