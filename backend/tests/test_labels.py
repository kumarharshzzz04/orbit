from __future__ import annotations

import sys

import pandas as pd
import pytest

from ml_sandbox import labels
from ml_sandbox.preprocess import LightCurveUnavailable, download_kepler_light_curve


def raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "kepid": [1, 1, 2, 3, 4, 5],
            "kepoi_name": [
                "K1.01 ",
                "K1.01",
                "K2.01",
                "K3.01",
                "K4.01",
                "K5.01",
            ],
            "koi_disposition": [
                "confirmed",
                "CANDIDATE",
                "FALSE POSITIVE",
                "CONFIRMED",
                "CANDIDATE",
                "false positive",
            ],
            "koi_period": [2.0, 2.5, 0.0, 4.0, 5.0, 6.0],
            "koi_time0bk": [0.0] * 6,
            "koi_duration": [1.0] * 6,
            "koi_depth": [100, 200, 300, 400, 500, 600],
            "koi_prad": [1.0] * 6,
            "koi_steff": [5000.0] * 6,
            "koi_slogg": [4.4] * 6,
            "koi_srad": [1.0] * 6,
            "koi_count": [2, 2, 1, 1, 1, 1],
            "koi_impact": [0.1] * 6,
            "koi_model_snr": [10.0] * 6,
        }
    )


def test_prepare_labels_normalizes_and_filters() -> None:
    prepared = labels.prepare_koi_labels(raw_frame())
    assert list(prepared["target_id"]) == ["K1.01", "K3.01", "K4.01", "K5.01"]
    assert list(prepared["label"]) == [1, 1, 1, 0]
    assert list(prepared["host_star"]) == ["1", "3", "4", "5"]
    assert prepared["koi_period"].dtype.kind == "f"
    # K2.01 has a zero period and must be dropped; the duplicate K1.01 collapses.
    assert "K2.01" not in set(prepared["target_id"])
    assert len(prepared) == 4


def test_prepare_labels_requires_columns() -> None:
    frame = raw_frame().drop(columns=["koi_period"])
    with pytest.raises(labels.LabelError, match="missing columns"):
        labels.prepare_koi_labels(frame)


def test_cached_koi_csv_is_read_without_network(tmp_path, monkeypatch) -> None:
    path = tmp_path / "koi.csv"
    raw_frame().to_csv(path, index=False)

    def no_network(*args, **kwargs):
        raise AssertionError("network should not be used when the CSV exists")

    monkeypatch.setattr(labels.urllib.request, "urlopen", no_network)
    frame = labels.fetch_koi_table(path)
    assert len(frame) == 6
    assert list(frame.columns) == list(raw_frame().columns)


def test_missing_lightkurve_gives_actionable_error(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "lightkurve", None)
    with pytest.raises(LightCurveUnavailable, match="lightkurve"):
        download_kepler_light_curve(11446443)
