"""Deterministic synthetic KOI population for offline mode.

Stub mode is a feature, not shame: it exercises the exact same preprocessing,
splitting and evaluation path as live data, on a laptop with no network. Each
target gets its own seeded RNG, so rebuilding a cache with the same
``(seed, targets)`` produces identical vectors regardless of order.

The population is physically motivated: false positives are usually eclipsing
binaries, so they get unequal odd/even depths and deep secondary eclipses;
planets get shallow secondary eclipses and equal odd/even depths.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from .preprocess import KEPLER_LONG_CADENCE_DAYS

BASE_KEPID = 1_000_000


def stable_seed(text: str) -> int:
    """Stable 64-bit seed for a string, independent of Python's hash salt."""
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def _trapezoid(
    phase_days: np.ndarray,
    duration_days: float,
    ingress_fraction: float = 0.2,
) -> np.ndarray:
    if not np.isfinite(duration_days) or duration_days <= 0:
        return np.zeros_like(phase_days, dtype=np.float64)
    half = 0.5 * duration_days
    x = np.abs(phase_days) / half
    shape = np.zeros_like(phase_days, dtype=np.float64)
    flat = 1.0 - ingress_fraction
    shape[x <= flat] = 1.0
    edge = (x > flat) & (x < 1.0)
    shape[edge] = 0.5 * (1.0 + np.cos(np.pi * (x[edge] - flat) / ingress_fraction))
    return shape


def _host_attributes(host_index: int, seed: int) -> dict[str, float]:
    rng = np.random.default_rng(stable_seed(f"{seed}:host:{host_index}"))
    return {
        "koi_steff": float(np.clip(rng.normal(5700.0, 480.0), 4000.0, 7000.0)),
        "koi_slogg": float(np.clip(rng.normal(4.4, 0.22), 3.5, 5.0)),
        "koi_srad": float(np.clip(10 ** rng.normal(0.0, 0.16), 0.4, 3.0)),
        "variability_ppm": float(rng.uniform(40.0, 320.0)),
        "variability_period_d": float(rng.uniform(6.0, 26.0)),
        "red_noise_ppm": float(rng.uniform(30.0, 110.0)),
        "white_noise_ppm": float(rng.uniform(80.0, 180.0)),
    }


def make_stub_labels(n_targets: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Build a deterministic KOI-like label table with host-level groupings."""
    if n_targets < 10:
        raise ValueError("n_targets must be >= 10")

    n_hosts = max(1, int(np.ceil(n_targets / 1.35)))
    targets_per_host = [1] * n_hosts
    extra_rng = np.random.default_rng(stable_seed(f"{seed}:host-allocation"))
    for _ in range(n_targets - n_hosts):
        available = np.flatnonzero(np.asarray(targets_per_host) < 4)
        targets_per_host[int(extra_rng.choice(available))] += 1

    rows: list[dict[str, float | int | str]] = []
    for host_index, n_planets in enumerate(targets_per_host):
        host = _host_attributes(host_index, seed)
        kepid = BASE_KEPID + host_index * 11
        for planet_index in range(n_planets):
            rng = np.random.default_rng(
                stable_seed(f"{seed}:target:{host_index}:{planet_index}")
            )
            period = float(10 ** rng.uniform(-0.12, 2.08))
            duration_hours = float(
                np.clip(
                    (2.2 + 2.6 * np.log10(period + 1.0)) * rng.lognormal(0.0, 0.22),
                    1.0,
                    20.0,
                )
            )
            depth_ppm = float(10 ** rng.uniform(np.log10(80.0), np.log10(15000.0)))
            impact = float(rng.beta(1.4, 2.4))
            t0 = float(rng.uniform(0.0, period))
            radius_ratio = np.sqrt(depth_ppm * 1e-6)
            planet_radius = float(
                np.clip(
                    radius_ratio
                    * host["koi_srad"]
                    * 109.076
                    * rng.lognormal(0.0, 0.07),
                    0.3,
                    30.0,
                )
            )
            model_snr = float(
                np.clip(
                    (depth_ppm / 110.0)
                    * np.sqrt(duration_hours / 4.0)
                    * rng.lognormal(0.0, 0.25),
                    1.2,
                    400.0,
                )
            )

            score = (
                0.045 * (model_snr - 20.0)
                + 0.00018 * (depth_ppm - 1500.0)
                - 1.1 * (impact - 0.5)
                - 0.010 * (period - 20.0)
                + rng.normal(0.0, 0.75)
            )

            target_id = f"K{host_index:05d}.{planet_index + 1:02d}"
            rows.append(
                {
                    "kepid": kepid,
                    "kepoi_name": target_id,
                    "koi_period": period,
                    "koi_time0bk": t0,
                    "koi_impact": impact,
                    "koi_duration": duration_hours,
                    "koi_depth": depth_ppm,
                    "koi_prad": planet_radius,
                    "koi_model_snr": model_snr,
                    "koi_count": n_planets,
                    "target_id": target_id,
                    "host_star": str(kepid),
                    "planet_score": float(score),
                    **host,
                }
            )

    frame = pd.DataFrame(rows)
    threshold = float(frame["planet_score"].median())
    frame["is_planet"] = (frame["planet_score"] > threshold).astype(int)

    dispositions = []
    odd_even = []
    secondary = []
    for row in frame.itertuples(index=False):
        rng = np.random.default_rng(stable_seed(f"{seed}:disposition:{row.target_id}"))
        if row.is_planet:
            dispositions.append("CONFIRMED" if rng.random() < 0.82 else "CANDIDATE")
            odd_even.append(abs(rng.normal(0.0, 0.004)))
            secondary.append(rng.uniform(0.004, 0.025))
        else:
            dispositions.append(
                "FALSE POSITIVE" if rng.random() < 0.88 else "CANDIDATE"
            )
            if rng.random() < 0.80:
                odd_even.append(rng.uniform(0.06, 0.35))
                secondary.append(rng.uniform(0.20, 0.75))
            else:
                odd_even.append(rng.uniform(0.005, 0.05))
                secondary.append(rng.uniform(0.01, 0.08))

    frame["koi_disposition"] = dispositions
    frame["label"] = frame["koi_disposition"].ne("FALSE POSITIVE").astype(int)
    frame["odd_even_frac"] = odd_even
    frame["secondary_frac"] = secondary
    frame = frame.drop(columns=["planet_score"])
    return frame.sort_values("target_id").reset_index(drop=True)


def generate_stub_light_curve(
    row: pd.Series | dict[str, object],
    *,
    seed: int = 42,
    baseline_days: float = 360.0,
    cadence_days: float = KEPLER_LONG_CADENCE_DAYS,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate one synthetic Kepler-like light curve."""
    data = dict(row)
    target_id = str(data["kepoi_name"])
    rng = np.random.default_rng(stable_seed(f"{seed}:curve:{target_id}"))

    n_points = int(baseline_days / cadence_days)
    time = np.arange(n_points, dtype=np.float64) * cadence_days
    time += float(rng.uniform(0.0, 5.0))

    keep = np.ones(n_points, dtype=bool)
    for _ in range(2):
        start = int(rng.integers(0, max(1, n_points // 2)))
        length = int(rng.integers(max(1, n_points // 30), max(2, n_points // 18)))
        keep[start : start + length] = False
    keep &= rng.random(n_points) > 0.004
    time = time[keep]

    period = float(data["koi_period"])
    t0 = float(data["koi_time0bk"])
    duration_days = float(data["koi_duration"]) / 24.0
    depth = float(data["koi_depth"]) * 1e-6
    odd_even = float(data["odd_even_frac"])
    secondary = float(data["secondary_frac"])

    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    shape = _trapezoid(phase, duration_days)
    transit_number = np.floor((time - t0) / period + 0.5).astype(np.int64)
    odd_transit = (transit_number % 2) == 1
    depth_multiplier = np.where(odd_transit, 1.0 + odd_even / 2.0, 1.0 - odd_even / 2.0)
    flux = 1.0 - depth * depth_multiplier * shape

    secondary_phase = (
        (time - t0 - 0.5 * period + 0.5 * period) % period
    ) - 0.5 * period
    flux -= depth * secondary * _trapezoid(secondary_phase, duration_days * 1.05)

    amplitude = float(data["variability_ppm"]) * 1e-6
    variability_period = float(data["variability_period_d"])
    flux *= (
        1.0
        + amplitude * np.sin(2.0 * np.pi * time / variability_period + 0.7)
        + 0.35
        * amplitude
        * np.sin(2.0 * np.pi * time / (variability_period * 2.7) + 2.1)
    )

    rho = 0.985
    red_noise = (
        lfilter([1.0], [1.0, -rho], rng.normal(0.0, 1.0, time.size))
        * float(data["red_noise_ppm"])
        * 1e-6
        * np.sqrt(1.0 - rho**2)
    )
    flux += red_noise + rng.normal(
        0.0, float(data["white_noise_ppm"]) * 1e-6, time.size
    )

    outliers = rng.random(time.size) < 0.0015
    if outliers.any():
        signs = rng.choice([-1.0, 1.0], size=int(outliers.sum()))
        flux[outliers] *= 1.0 + signs * rng.uniform(0.02, 0.08, int(outliers.sum()))

    return time, flux
