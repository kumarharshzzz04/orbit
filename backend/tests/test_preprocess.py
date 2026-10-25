from __future__ import annotations

import numpy as np
import pytest

from ml_sandbox import preprocess, stub
from ml_sandbox.preprocess import KEPLER_LONG_CADENCE_DAYS, PreprocessError


def synthetic_curve(
    *,
    seed: int = 0,
    depth_ppm: float = 2000.0,
    noise_ppm: float = 40.0,
    period: float = 6.3,
    duration_hours: float = 3.2,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    time = np.arange(0.0, 120.0, KEPLER_LONG_CADENCE_DAYS)
    t0 = 0.7
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    in_transit = np.abs(phase) <= 0.5 * duration_hours / 24.0
    flux = 1.0 - depth_ppm * 1e-6 * in_transit.astype(float)
    flux += rng.normal(0.0, noise_ppm * 1e-6, time.size)
    return time, flux


def test_preprocess_is_deterministic() -> None:
    time, flux = synthetic_curve()
    first = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        n_bins=400,
        expected_depth_ppm=2000,
    )
    second = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        n_bins=400,
        expected_depth_ppm=2000,
    )
    np.testing.assert_array_equal(first.flux, second.flux)
    assert first.measured["measured_depth_ppm"] == second.measured["measured_depth_ppm"]


def test_fold_has_requested_number_of_finite_bins() -> None:
    time, flux = synthetic_curve()
    folded = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        n_bins=400,
        expected_depth_ppm=2000,
    )
    assert folded.flux.shape == (400,)
    assert np.isfinite(folded.flux).all()
    assert 0.9 < float(np.median(folded.flux)) < 1.1


def test_measured_depth_recovers_injected_transit() -> None:
    time, flux = synthetic_curve(depth_ppm=2000.0, noise_ppm=30.0)
    folded = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        n_bins=400,
        expected_depth_ppm=2000,
    )
    depth = folded.measured["measured_depth_ppm"]
    assert np.isfinite(depth)
    assert 1500 < depth < 2500


def test_isolated_spike_is_removed_without_touching_the_transit() -> None:
    time, flux = synthetic_curve()
    spiked = flux.copy()
    index = int(np.argmax(time))
    spiked[index] *= 1.08

    kept_time, kept_flux = preprocess.sigma_clip(time, spiked, protect_depth_ppm=2000)
    assert len(kept_time) == len(time) - 1
    assert float(np.max(kept_flux)) < 1.05

    clean = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        expected_depth_ppm=2000,
    )
    clipped = preprocess.preprocess_light_curve(
        time,
        spiked,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        expected_depth_ppm=2000,
    )
    # A removed cadence can shift one sparse phase bin; the fold as a whole and
    # the measured depth must stay put.
    assert float(np.median(np.abs(clean.flux - clipped.flux))) < 1e-4
    np.testing.assert_allclose(clean.flux, clipped.flux, atol=1e-2)
    assert (
        abs(
            clean.measured["measured_depth_ppm"]
            - clipped.measured["measured_depth_ppm"]
        )
        < 100
    )


def test_empty_phase_bins_fill_with_continuum() -> None:
    time, flux = synthetic_curve(period=400.0, duration_hours=3.2)
    folded = preprocess.preprocess_light_curve(
        time,
        flux,
        period=400.0,
        t0=0.7,
        duration_hours=3.2,
        n_bins=400,
        expected_depth_ppm=2000,
    )
    assert np.isfinite(folded.flux).all()
    assert int(np.sum(folded.flux == 1.0)) > 250


def test_raw_flux_scale_does_not_change_the_fold() -> None:
    time, flux = synthetic_curve(depth_ppm=10_000.0, noise_ppm=80.0)
    relative = preprocess.preprocess_light_curve(
        time,
        flux,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        expected_depth_ppm=10_000,
    )
    raw = preprocess.preprocess_light_curve(
        time,
        flux * 404_361.0,
        period=6.3,
        t0=0.7,
        duration_hours=3.2,
        expected_depth_ppm=10_000,
    )
    np.testing.assert_allclose(relative.flux, raw.flux, atol=1e-4)
    assert relative.measured["measured_depth_ppm"] == pytest.approx(
        raw.measured["measured_depth_ppm"], rel=1e-3
    )
    assert raw.measured["measured_depth_ppm"] > 8000


def test_bad_inputs_raise() -> None:
    with pytest.raises(PreprocessError):
        preprocess.preprocess_light_curve(
            np.arange(10.0),
            np.ones(10),
            period=2.0,
            t0=0.0,
            duration_hours=2.0,
        )
    with pytest.raises(PreprocessError):
        preprocess.preprocess_light_curve(
            np.arange(100.0),
            np.ones(99),
            period=2.0,
            t0=0.0,
            duration_hours=2.0,
        )
    with pytest.raises(PreprocessError):
        preprocess.fold_phase_days(np.arange(100.0), 0.0, 0.0)


def test_odd_even_feature_detects_eclipsing_binary() -> None:
    frame = stub.make_stub_labels(n_targets=40, seed=11)
    candidates = frame[(frame["is_planet"] == 0) & (frame["odd_even_frac"] > 0.2)]
    if candidates.empty:  # pragma: no cover - depends on random population
        pytest.skip("stub population had no deep odd/even false positive")
    row = candidates.iloc[0]
    time, flux = stub.generate_stub_light_curve(row, seed=11)
    folded = preprocess.preprocess_light_curve(
        time,
        flux,
        period=float(row["koi_period"]),
        t0=float(row["koi_time0bk"]),
        duration_hours=float(row["koi_duration"]),
        n_bins=400,
        expected_depth_ppm=float(row["koi_depth"]),
    )
    assert folded.measured["odd_even_diff"] > 0.05


def test_cadence_estimate_handles_gaps() -> None:
    time = np.concatenate(
        [
            np.arange(0.0, 10.0, KEPLER_LONG_CADENCE_DAYS),
            np.arange(20.0, 30.0, KEPLER_LONG_CADENCE_DAYS),
        ]
    )
    cadence = preprocess.estimate_cadence_days(time)
    assert cadence == pytest.approx(KEPLER_LONG_CADENCE_DAYS, rel=1e-6)
