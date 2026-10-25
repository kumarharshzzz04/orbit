from __future__ import annotations

import numpy as np
import pytest

from ml_sandbox import evaluate


def test_perfect_predictions_score_one() -> None:
    result = evaluate.evaluate_predictions(
        np.array([0, 0, 1, 1]),
        np.array(["FALSE POSITIVE", "FALSE POSITIVE", "CONFIRMED", "CONFIRMED"]),
        np.array([0.1, 0.2, 0.8, 0.9]),
        threshold=0.5,
    )
    for name, value in result.metrics.items():
        assert value == pytest.approx(1.0), name
    assert result.confusion["primary"] == {"tn": 2, "fp": 0, "fn": 0, "tp": 2, "n": 4}
    assert result.roc_auc_defined is True


def test_metrics_match_known_counts() -> None:
    result = evaluate.evaluate_predictions(
        np.array([1, 1, 1, 0]),
        np.array(["CONFIRMED", "CONFIRMED", "CONFIRMED", "FALSE POSITIVE"]),
        np.array([0.9, 0.6, 0.2, 0.7]),
        threshold=0.5,
    )
    # tp=2, fp=1, fn=1, tn=0
    assert result.metrics["accuracy"] == pytest.approx(0.5)
    assert result.metrics["precision"] == pytest.approx(2 / 3)
    assert result.metrics["recall"] == pytest.approx(2 / 3)
    assert result.metrics["f1"] == pytest.approx(2 / 3)
    assert result.confusion["primary"] == {"tn": 0, "fp": 1, "fn": 1, "tp": 2, "n": 4}


def test_candidates_are_excluded_from_primary_metrics() -> None:
    result = evaluate.evaluate_predictions(
        np.array([1, 0, 1]),
        np.array(["CONFIRMED", "FALSE POSITIVE", "CANDIDATE"]),
        np.array([0.9, 0.1, 0.4]),
        threshold=0.5,
    )
    assert result.n_primary == 2
    assert result.n_all == 3
    assert result.metrics["f1"] == pytest.approx(1.0)
    assert result.candidate_inclusive["recall"] == pytest.approx(0.5)
    assert result.candidate_inclusive["accuracy"] == pytest.approx(2 / 3)
    assert result.confusion["candidate_inclusive"]["fn"] == 1


def test_single_class_auc_is_flagged_not_crashed() -> None:
    result = evaluate.evaluate_predictions(
        np.array([1, 1]),
        np.array(["CONFIRMED", "CONFIRMED"]),
        np.array([0.2, 0.9]),
        threshold=0.5,
    )
    assert result.roc_auc_defined is False
    assert result.metrics["roc_auc"] == 0.5
    assert result.single_class_primary is True


def test_all_candidates_fall_back_to_all_rows() -> None:
    result = evaluate.evaluate_predictions(
        np.array([1, 0]),
        np.array(["CANDIDATE", "CANDIDATE"]),
        np.array([0.9, 0.1]),
        threshold=0.5,
    )
    assert result.primary_fallback is True
    assert result.n_primary == 2


def test_threshold_selection_maximizes_f1_near_half() -> None:
    labels = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.4, 0.6, 0.9])
    choice = evaluate.select_threshold(labels, probabilities)
    assert 0.4 < choice.threshold <= 0.6
    assert choice.val_f1 == pytest.approx(1.0)
    assert choice.single_class is False


def test_threshold_selection_handles_empty_input() -> None:
    choice = evaluate.select_threshold(np.array([]), np.array([]))
    assert choice.threshold == 0.5
    assert choice.n_rows == 0
