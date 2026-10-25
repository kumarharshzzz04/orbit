"""KOI labels from the NASA Exoplanet Archive (TAP) with a local cache.

Primary truth for the gate is CONFIRMED vs FALSE POSITIVE. CANDIDATE labels are
kept in training (more data) but excluded from the primary test metric; the
evaluator reports candidate-inclusive numbers separately.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TAP_SYNC_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

KOI_COLUMNS = [
    "kepid",
    "kepoi_name",
    "koi_disposition",
    "koi_period",
    "koi_time0bk",
    "koi_impact",
    "koi_duration",
    "koi_depth",
    "koi_prad",
    "koi_model_snr",
    "koi_count",
    "koi_steff",
    "koi_slogg",
    "koi_srad",
]
NUMERIC_COLUMNS = [
    column for column in KOI_COLUMNS if column not in {"kepoi_name", "koi_disposition"}
]
DISPOSITIONS = ("CONFIRMED", "CANDIDATE", "FALSE POSITIVE")
REQUIRED_COLUMNS = {
    "kepid",
    "kepoi_name",
    "koi_disposition",
    "koi_period",
    "koi_time0bk",
    "koi_duration",
}


class LabelError(RuntimeError):
    """Raised when labels cannot be downloaded or parsed."""


def _tap_query() -> str:
    columns = ", ".join(KOI_COLUMNS)
    allowed = ", ".join(f"'{value}'" for value in DISPOSITIONS)
    return (
        f"select {columns} from cumulative "
        f"where koi_disposition in ({allowed}) "
        "order by kepoi_name"
    )


def _read_koi_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as exc:
        raise LabelError(f"could not read KOI cache {path}: {exc}") from exc


def fetch_koi_table(
    path: str | Path,
    *,
    refresh: bool = False,
    timeout: float = 180.0,
) -> pd.DataFrame:
    """Download the KOI cumulative table once and cache it as CSV."""
    csv_path = Path(path)
    meta_path = csv_path.with_suffix(csv_path.suffix + ".meta.json")

    if csv_path.exists() and not refresh:
        return _read_koi_csv(csv_path)

    query = _tap_query()
    url = TAP_SYNC_URL + "?" + urllib.parse.urlencode({"query": query, "format": "csv"})
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ORBIT-ml-sandbox/0.1 (hackathon research demo)",
            "Accept": "text/csv",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read()
    except Exception as exc:
        if csv_path.exists():
            warnings.warn(
                f"KOI download failed ({exc}); using cached labels at {csv_path}",
                stacklevel=2,
            )
            return _read_koi_csv(csv_path)
        raise LabelError(f"KOI table download failed: {exc}") from exc

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = csv_path.with_suffix(csv_path.suffix + ".tmp")
    temporary.write_bytes(body)
    temporary.replace(csv_path)

    metadata = {
        "query": query,
        "sha1": hashlib.sha1(body).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": len(body),
    }
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return _read_koi_csv(csv_path)


def prepare_koi_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize the raw KOI table into the canonical label frame."""
    frame = frame.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise LabelError(f"KOI table is missing columns: {', '.join(sorted(missing))}")

    frame["kepoi_name"] = frame["kepoi_name"].astype(str).str.strip()
    frame["koi_disposition"] = (
        frame["koi_disposition"].astype(str).str.strip().str.upper()
    )
    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame[frame["koi_disposition"].isin(DISPOSITIONS)]
    frame = frame.dropna(subset=["kepid", "koi_period", "koi_time0bk", "koi_duration"])
    frame = frame[
        (frame["koi_period"] > 0)
        & (frame["koi_duration"] > 0)
        & frame["kepoi_name"].ne("")
    ]
    frame = frame.drop_duplicates(subset=["kepoi_name"], keep="first")

    frame["target_id"] = frame["kepoi_name"]
    frame["host_star"] = frame["kepid"].astype("int64").astype(str)
    frame["label"] = frame["koi_disposition"].ne("FALSE POSITIVE").astype(int)
    frame = frame.sort_values("target_id").reset_index(drop=True)
    return frame


def load_koi_labels(
    path: str | Path,
    *,
    refresh: bool = False,
    timeout: float = 180.0,
) -> pd.DataFrame:
    raw = fetch_koi_table(path, refresh=refresh, timeout=timeout)
    return prepare_koi_labels(raw)
