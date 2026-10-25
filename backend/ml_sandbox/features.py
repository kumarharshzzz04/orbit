"""Named feature sets shared by cache building and training.

The cache always stores all 14 features. A config selects a subset, which is
how the agent loop can propose interpretable "add two vetting features" changes
without rebuilding the cache.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

CATALOG_FEATURES = [
    "log10_period",
    "duration_hours",
    "depth_ppm",
    "log1p_snr",
    "planet_radius_earth",
    "radius_ratio",
    "impact_parameter",
    "stellar_teff_k",
    "stellar_logg",
    "stellar_radius_sun",
    "n_companions",
    "duty_cycle",
]

FOLD_FEATURES = [
    "odd_even_diff",
    "secondary_depth_ratio",
]

FEATURE_NAMES = CATALOG_FEATURES + FOLD_FEATURES

FEATURE_SETS = {
    "catalog_v1": CATALOG_FEATURES,
    "vetting_v1": FEATURE_NAMES,
}

EARTH_RADIUS_IN_SUN_RADII = 109.076


def indices_for(feature_set: str) -> list[int]:
    """Column indices for a named feature set, in the set's declared order."""
    try:
        names = FEATURE_SETS[feature_set]
    except KeyError as exc:
        raise KeyError(f"unknown feature set {feature_set!r}") from exc
    return [FEATURE_NAMES.index(name) for name in names]


def _number(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    if value is None:
        return float("nan")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if np.isfinite(number) else float("nan")


def build_feature_vector(
    row: Mapping[str, object],
    fold_metrics: Mapping[str, float],
) -> np.ndarray:
    """Build the 14-feature vector for one target.

    Catalog columns come from the KOI table; the last two features are measured
    from the folded light curve (odd/even depth difference and secondary eclipse
    depth relative to the primary). Missing values stay NaN and are imputed by
    the model pipeline, never silently turned into zeros here.
    """
    period = _number(row, "koi_period")
    duration_hours = _number(row, "koi_duration")
    depth_ppm = _number(row, "koi_depth")
    snr = _number(row, "koi_model_snr")
    planet_radius = _number(row, "koi_prad")
    stellar_radius = _number(row, "koi_srad")
    impact = _number(row, "koi_impact")
    teff = _number(row, "koi_steff")
    logg = _number(row, "koi_slogg")
    companions = _number(row, "koi_count")

    log10_period = float(np.log10(period)) if period > 0 else float("nan")
    log1p_snr = float(np.log1p(max(snr, 0.0))) if np.isfinite(snr) else float("nan")
    duty_cycle = (
        (duration_hours / 24.0) / period
        if period > 0 and duration_hours > 0
        else float("nan")
    )
    radius_ratio = (
        planet_radius / (stellar_radius * EARTH_RADIUS_IN_SUN_RADII)
        if planet_radius > 0 and stellar_radius > 0
        else float("nan")
    )

    return np.asarray(
        [
            log10_period,
            duration_hours,
            depth_ppm,
            log1p_snr,
            planet_radius,
            radius_ratio,
            impact,
            teff,
            logg,
            stellar_radius,
            companions,
            duty_cycle,
            fold_metrics.get("odd_even_diff", float("nan")),
            fold_metrics.get("secondary_depth_ratio", float("nan")),
        ],
        dtype=np.float32,
    )
