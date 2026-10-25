"""Deterministic light-curve preprocessing.

Every function here is pure: same inputs -> same outputs, no hidden state, no
randomness. The cache stores only the result, and trainers load byte-identical
(well, content-identical) vectors for champion and challenger alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

# Kepler long cadence is 29.4 minutes.
KEPLER_LONG_CADENCE_DAYS = 29.4 / (24.0 * 60.0)
# Kepler time is BKJD = BJD - 2454833.0, matching koi_time0bk.
BKJD_OFFSET = 2454833.0


class PreprocessError(ValueError):
    """Raised when a light curve cannot be made into a usable fold."""


class LightCurveUnavailable(RuntimeError):
    """No downloadable Kepler light curve for a target."""


@dataclass
class FoldedLightCurve:
    flux: np.ndarray
    measured: dict[str, float] = field(default_factory=dict)
    n_points: int = 0

    def __post_init__(self) -> None:
        self.flux = np.asarray(self.flux, dtype=np.float32)


def _validate_inputs(
    time: np.ndarray, flux: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    time = np.asarray(time, dtype=np.float64).ravel()
    flux = np.asarray(flux, dtype=np.float64).ravel()
    if time.size != flux.size:
        raise PreprocessError("time and flux must have the same length")
    finite = np.isfinite(time) & np.isfinite(flux)
    time, flux = time[finite], flux[finite]
    if time.size < 50:
        raise PreprocessError(f"need at least 50 finite cadences, got {time.size}")
    order = np.argsort(time, kind="stable")
    return time[order], flux[order]


def estimate_cadence_days(time: np.ndarray) -> float:
    diffs = np.diff(np.sort(time))
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        raise PreprocessError("cannot estimate cadence from a single timestamp")
    return float(np.median(diffs))


def sigma_clip(
    time: np.ndarray,
    flux: np.ndarray,
    *,
    window_days: float = 1.0,
    sigma: float = 6.0,
    protect_depth_ppm: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Remove isolated spikes using a rolling-median residual.

    A rolling median follows the transit as it happens, so a real 3-10 hour
    transit is *not* treated as an outlier the way a global 5-sigma clip would.
    When the catalog transit depth is known, points no deeper than 1.5x that
    depth are always kept, which protects deep short transits from the clipper.
    """
    cadence = estimate_cadence_days(time)
    size = int(round(window_days / cadence))
    size = max(5, size)
    if size % 2 == 0:
        size += 1
    if size >= time.size:
        return time, flux
    if size % 2 == 0:
        size -= 1

    # Reflect (not nearest) so a spike at the first/last cadence is still seen
    # as a residual instead of being copied into its own local median.
    trend = median_filter(flux, size=size, mode="reflect")
    residual = flux - trend
    center = np.median(residual)
    mad = np.median(np.abs(residual - center))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= 0:
        return time, flux
    threshold = sigma * scale
    if protect_depth_ppm is not None and np.isfinite(protect_depth_ppm):
        # The protection depth is in ppm of the *relative* flux. Scale it by
        # the median so this also works when the caller passes raw e-/s.
        relative_depth = 1.5 * abs(float(protect_depth_ppm)) * 1e-6
        threshold = max(threshold, relative_depth * abs(float(np.median(flux))))
    keep = np.abs(residual - center) <= threshold
    if keep.sum() < 50:
        return time, flux
    return time[keep], flux[keep]


def detrend_and_normalize(
    time: np.ndarray,
    flux: np.ndarray,
    *,
    window_days: float = 5.0,
    polyorder: int = 3,
) -> np.ndarray:
    """Savitzky-Golay detrend, then normalize the median to 1."""
    cadence = estimate_cadence_days(time)
    window = int(round(window_days / cadence))
    if window % 2 == 0:
        window += 1
    max_window = time.size if time.size % 2 == 1 else time.size - 1
    window = min(window, max_window)
    if window <= polyorder:
        normalized = flux / np.median(flux)
    else:
        trend = savgol_filter(
            flux, window_length=window, polyorder=polyorder, mode="interp"
        )
        trend = np.where(np.abs(trend) < 1e-12, np.median(flux), trend)
        normalized = flux / trend
    median = np.median(normalized)
    if not np.isfinite(median) or abs(median) < 1e-12:
        raise PreprocessError("cannot normalize light curve (zero median)")
    return normalized / median


def fold_phase_days(time: np.ndarray, period: float, t0: float) -> np.ndarray:
    """Phase in days, folded at ``t0``, wrapped to [-period/2, period/2)."""
    if not np.isfinite(period) or period <= 0:
        raise PreprocessError(f"invalid period: {period!r}")
    return ((time - t0 + 0.5 * period) % period) - 0.5 * period


def fold_and_bin(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    n_bins: int = 400,
) -> np.ndarray:
    """Average the folded flux into ``n_bins`` phase bins.

    Empty bins (data gaps) are filled with the out-of-transit continuum value 1.
    """
    if n_bins < 10:
        raise PreprocessError("n_bins must be >= 10")
    phase = fold_phase_days(time, period, t0) / period
    indices = np.floor((phase + 0.5) * n_bins).astype(np.int64)
    np.clip(indices, 0, n_bins - 1, out=indices)

    sums = np.bincount(indices, weights=flux, minlength=n_bins)
    counts = np.bincount(indices, minlength=n_bins)
    binned = np.ones(n_bins, dtype=np.float64)
    populated = counts > 0
    binned[populated] = sums[populated] / counts[populated]
    binned = np.nan_to_num(binned, nan=1.0, posinf=2.0, neginf=0.0)
    return np.clip(binned, 0.0, 2.0).astype(np.float32)


def measure_transit_features(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration_hours: float,
) -> dict[str, float]:
    """Measure the vetting diagnostics used by the ``vetting_v1`` feature set.

    These are deliberately physical: an eclipsing binary usually shows unequal
    odd/even depths and a deep secondary eclipse; a planet does not.
    """
    nan = float("nan")
    result = {
        "measured_depth_ppm": nan,
        "measured_snr": nan,
        "odd_even_diff": nan,
        "secondary_depth_ratio": nan,
        "n_in_transit": 0.0,
        "n_secondary": 0.0,
    }
    if not np.isfinite(duration_hours) or duration_hours <= 0:
        return result
    if not np.isfinite(period) or period <= 0:
        return result

    phase = fold_phase_days(time, period, t0)
    phase_norm = phase / period
    duration_days = duration_hours / 24.0
    half_duration_norm = 0.5 * duration_days / period
    # 10% padding tolerates catalog ephemeris/timing errors.
    in_transit = np.abs(phase_norm) <= 1.10 * half_duration_norm
    out_of_transit = ~in_transit
    if in_transit.sum() < 3 or out_of_transit.sum() < 10:
        return result

    out_flux = flux[out_of_transit]
    depth = 1.0 - float(np.median(flux[in_transit]))
    depth = max(depth, 0.0)
    result["n_in_transit"] = float(in_transit.sum())
    result["measured_depth_ppm"] = depth * 1e6

    noise = 1.4826 * float(np.median(np.abs(out_flux - np.median(out_flux))))
    if np.isfinite(noise) and noise > 1e-9:
        result["measured_snr"] = depth / noise * np.sqrt(float(in_transit.sum()))

    transit_number = np.floor((time - t0) / period + 0.5).astype(np.int64)
    odd = in_transit & (transit_number % 2 == 1)
    even = in_transit & (transit_number % 2 == 0)
    if odd.sum() >= 3 and even.sum() >= 3:
        odd_depth = 1.0 - float(np.median(flux[odd]))
        even_depth = 1.0 - float(np.median(flux[even]))
        result["odd_even_diff"] = float(
            np.clip(abs(odd_depth - even_depth) / (depth + 1e-6), 0.0, 5.0)
        )

    secondary = (
        np.abs(np.abs(phase_norm) - 0.5) <= 1.6 * half_duration_norm
    ) & ~in_transit
    secondary_flux = flux[secondary]
    if secondary_flux.size >= 3:
        secondary_depth = max(0.0, 1.0 - float(np.median(secondary_flux)))
        result["n_secondary"] = float(secondary_flux.size)
        result["secondary_depth_ratio"] = float(
            np.clip(secondary_depth / (depth + 1e-6), 0.0, 5.0)
        )
    return result


def preprocess_light_curve(
    time: np.ndarray,
    flux: np.ndarray,
    *,
    period: float,
    t0: float,
    duration_hours: float,
    n_bins: int = 400,
    expected_depth_ppm: float | None = None,
) -> FoldedLightCurve:
    """Full pipeline: normalize -> clip -> detrend -> fold -> bin + diagnostics."""
    time, flux = _validate_inputs(time, flux)
    median = float(np.median(flux))
    if not np.isfinite(median) or median <= 0:
        raise PreprocessError("light curve must have a positive finite median")
    # Work in relative flux from here on: thresholds and Savitzky-Golay are
    # scale-free, and raw PDCSAP values are e-/s (hundreds of thousands).
    relative = flux / median
    time, relative = sigma_clip(time, relative, protect_depth_ppm=expected_depth_ppm)
    normalized = detrend_and_normalize(time, relative)
    measured = measure_transit_features(
        time, normalized, period=period, t0=t0, duration_hours=duration_hours
    )
    folded = fold_and_bin(time, normalized, period=period, t0=t0, n_bins=n_bins)
    return FoldedLightCurve(flux=folded, measured=measured, n_points=int(time.size))


def download_kepler_light_curve(
    kepid: int,
    download_dir: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Download + stitch Kepler long-cadence PDCSAP flux via lightkurve.

    Heavy astronomy dependencies are optional and imported lazily so stub mode
    and CI never need them.
    """
    try:
        import lightkurve as lk  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only without astro deps
        raise LightCurveUnavailable(
            "lightkurve is not installed; use DATA_MODE=stub or "
            "pip install -r requirements-astro.txt"
        ) from exc

    if download_dir is not None:
        Path(download_dir).mkdir(parents=True, exist_ok=True)

    try:
        search = lk.search_lightcurve(
            f"KIC {int(kepid)}",
            mission="Kepler",
            cadence="long",
        )
    except Exception as exc:  # pragma: no cover - network path
        raise LightCurveUnavailable(
            f"MAST search failed for KIC {kepid}: {exc}"
        ) from exc

    if len(search) == 0:
        raise LightCurveUnavailable(f"no Kepler long-cadence data for KIC {kepid}")

    try:
        collection = search.download_all(download_dir=str(download_dir))
    except Exception as exc:  # pragma: no cover - network path
        raise LightCurveUnavailable(
            f"MAST download failed for KIC {kepid}: {exc}"
        ) from exc
    if collection is None:
        raise LightCurveUnavailable(f"MAST returned no products for KIC {kepid}")

    light_curve = collection.stitch()
    if light_curve is None:
        raise LightCurveUnavailable(f"could not stitch quarters for KIC {kepid}")
    light_curve = light_curve.remove_nans()

    flux_quantity = getattr(light_curve, "pdcsap_flux", None)
    if flux_quantity is None:
        flux_quantity = light_curve.flux
    flux = np.asarray(flux_quantity, dtype=np.float64)
    time = np.asarray(light_curve.time.value, dtype=np.float64)
    # Defensive: some readers present full JD instead of BKJD.
    if time.size and np.nanmedian(time) > 1e6:
        time = time - BKJD_OFFSET
    if not np.isfinite(flux).any():
        raise LightCurveUnavailable(f"all-NaN PDCSAP flux for KIC {kepid}")
    return time, flux
