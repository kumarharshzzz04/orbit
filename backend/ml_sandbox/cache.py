"""Cache folded light curves and features as one ``.npz`` per target.

The manifest is the dataset identity: each entry carries a content hash of the
arrays, and the dataset fingerprint hashes the sorted entries together with the
label and feature schema. Training verifies those hashes before fitting, so a
champion and a challenger can only ever see the same bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import features, preprocess, stub

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
PACKED_NAME = "packed.npz"

ProgressCallback = Callable[[dict[str, Any]], None]


class CacheError(RuntimeError):
    """Raised when a cache is inconsistent or cannot be built."""


def content_sha1(
    flux: np.ndarray,
    feature_vector: np.ndarray,
    feature_names: list[str] | None = None,
) -> str:
    """Content hash of the stored arrays (npz zip timestamps are irrelevant)."""
    names = feature_names or features.FEATURE_NAMES
    digest = hashlib.sha1()
    digest.update(b"orbit-ml-cache-v1\0")
    digest.update(np.asarray(flux, dtype="<f4").tobytes(order="C"))
    digest.update(np.asarray(feature_vector, dtype="<f4").tobytes(order="C"))
    digest.update("|".join(names).encode("utf-8"))
    return digest.hexdigest()


def dataset_fingerprint(
    entries: dict[str, dict[str, Any]],
    *,
    n_bins: int,
    feature_names: list[str] | None = None,
) -> str:
    """Deterministic identity for the whole cached dataset."""
    names = feature_names or features.FEATURE_NAMES
    targets = [
        {
            "id": target_id,
            "host": entries[target_id]["host_star"],
            "label": int(entries[target_id]["label"]),
            "disposition": entries[target_id]["disposition"],
            "content": entries[target_id]["content_sha1"],
        }
        for target_id in sorted(entries)
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "n_bins": n_bins,
        "feature_names": names,
        "targets": targets,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def manifest_path(cache_dir: str | Path) -> Path:
    return Path(cache_dir) / MANIFEST_NAME


def load_manifest(cache_dir: str | Path) -> dict[str, Any] | None:
    path = manifest_path(cache_dir)
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CacheError(f"cache manifest is not valid JSON: {path}: {exc}") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CacheError(
            f"cache {path} uses schema {manifest.get('schema_version')}, "
            f"this code expects {SCHEMA_VERSION}"
        )
    return manifest


def _write_manifest(cache_dir: Path, manifest: dict[str, Any]) -> None:
    path = manifest_path(cache_dir)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _write_target_npz(
    path: Path,
    flux: np.ndarray,
    feature_vector: np.ndarray,
) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        np.savez(
            handle,
            flux=np.asarray(flux, dtype=np.float32),
            features=np.asarray(feature_vector, dtype=np.float32),
            feature_names=np.asarray(features.FEATURE_NAMES),
        )
    os.replace(temporary, path)


def read_target_npz(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(Path(path)) as data:
        flux = np.asarray(data["flux"], dtype=np.float32)
        feature_vector = np.asarray(data["features"], dtype=np.float32)
    return flux, feature_vector


def packed_content_sha1(
    target_ids: list[str],
    flux: np.ndarray,
    feature_matrix: np.ndarray,
) -> str:
    """Content hash of the packed matrices, independent of npz timestamps."""
    digest = hashlib.sha1()
    digest.update(b"orbit-packed-v1\0")
    digest.update("\n".join(target_ids).encode("utf-8"))
    digest.update(np.asarray(flux, dtype="<f4").tobytes(order="C"))
    digest.update(np.asarray(feature_matrix, dtype="<f4").tobytes(order="C"))
    digest.update("|".join(features.FEATURE_NAMES).encode("utf-8"))
    return digest.hexdigest()


def _write_packed(
    cache_dir: Path,
    target_ids: list[str],
    flux: np.ndarray,
    feature_matrix: np.ndarray,
    dataset_fp: str,
) -> dict[str, Any]:
    path = cache_dir / PACKED_NAME
    content = packed_content_sha1(target_ids, flux, feature_matrix)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        np.savez(
            handle,
            target_ids=np.asarray(target_ids, dtype="U16"),
            flux=np.asarray(flux, dtype=np.float32),
            features=np.asarray(feature_matrix, dtype=np.float32),
            feature_names=np.asarray(features.FEATURE_NAMES),
            dataset_fingerprint=np.asarray(dataset_fp),
            content_sha1=np.asarray(content),
        )
    os.replace(temporary, path)
    return {"file": PACKED_NAME, "content_sha1": content, "n_targets": len(target_ids)}


def _ensure_packed(
    cache_dir: Path,
    entries: dict[str, dict[str, Any]],
    dataset_fp: str,
    fresh: dict[str, tuple[np.ndarray, np.ndarray]],
) -> dict[str, Any] | None:
    """Write the fast-path packed matrix, reusing fresh in-memory arrays."""
    target_ids = sorted(entries)
    existing = load_manifest(cache_dir)
    if existing is not None:
        packed = existing.get("packed")
        if (
            isinstance(packed, dict)
            and existing.get("dataset_fingerprint") == dataset_fp
            and (cache_dir / packed.get("file", PACKED_NAME)).exists()
        ):
            try:
                if read_packed(cache_dir, existing) is not None:
                    return packed
            except CacheError:
                pass  # repack from the per-target files

    flux_rows: list[np.ndarray] = []
    feature_rows: list[np.ndarray] = []
    try:
        for target_id in target_ids:
            if target_id in fresh:
                flux, feature_vector = fresh[target_id]
            else:
                flux, feature_vector = read_target_npz(
                    cache_dir / entries[target_id]["path"]
                )
            flux_rows.append(flux)
            feature_rows.append(feature_vector)
    except (OSError, ValueError, KeyError):
        return None
    return _write_packed(
        cache_dir,
        target_ids,
        np.vstack(flux_rows).astype(np.float32),
        np.vstack(feature_rows).astype(np.float32),
        dataset_fp,
    )


def read_packed(
    cache_dir: str | Path,
    manifest: dict[str, Any],
) -> tuple[list[str], np.ndarray, np.ndarray] | None:
    """Load the packed matrix, or None when the cache predates packing.

    A packed file that exists but fails verification raises ``CacheError``: a
    corrupt fast path must not silently fall back to a slow path and hide it.
    """
    packed = manifest.get("packed")
    if not isinstance(packed, dict):
        return None
    path = Path(cache_dir) / str(packed.get("file", PACKED_NAME))
    if not path.exists():
        return None
    try:
        with np.load(path) as data:
            target_ids = [str(value) for value in data["target_ids"]]
            flux = np.asarray(data["flux"], dtype=np.float32)
            feature_matrix = np.asarray(data["features"], dtype=np.float32)
            stored_hash = str(data["content_sha1"])
            stored_fp = str(data["dataset_fingerprint"])
            stored_names = [str(value) for value in data["feature_names"]]
    except (OSError, ValueError, KeyError) as exc:
        raise CacheError(f"packed cache is unreadable: {path}: {exc}") from exc

    if stored_names != features.FEATURE_NAMES:
        raise CacheError("packed cache feature schema does not match this code")
    if stored_fp != manifest.get("dataset_fingerprint"):
        raise CacheError("packed cache belongs to a different dataset fingerprint")
    if stored_hash != packed.get("content_sha1"):
        raise CacheError("packed cache manifest hash does not match the file")
    if sorted(target_ids) != sorted(manifest.get("targets", {})):
        raise CacheError("packed cache ids do not match the manifest")
    if stored_hash != packed_content_sha1(target_ids, flux, feature_matrix):
        raise CacheError(
            "packed cache content hash mismatch; rebuild the cache to restore it"
        )
    if flux.shape != (len(target_ids), manifest.get("n_bins")):
        raise CacheError("packed cache flux shape is wrong")
    if feature_matrix.shape != (len(target_ids), len(features.FEATURE_NAMES)):
        raise CacheError("packed cache feature shape is wrong")
    return target_ids, flux, feature_matrix


@dataclass
class CacheBuildReport:
    mode: str
    cache_dir: str
    processed: int
    cached: int
    new: int
    reused: int
    skipped: int
    dataset_fingerprint: str
    seconds: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "mode": self.mode,
            "cache": self.cache_dir,
            "processed": self.processed,
            "cached": self.cached,
            "new": self.new,
            "reused": self.reused,
            "skipped": self.skipped,
            "dataset_fingerprint": self.dataset_fingerprint,
            "seconds": round(self.seconds, 3),
        }


def _live_download_worker(
    kepid: int, download_dir: str
) -> tuple[np.ndarray, np.ndarray]:
    """Top-level worker for process-isolated MAST downloads.

    astroquery/lightkurve are not thread-safe: running downloads in threads
    closes shared stdout handles and poisons the rest of the build. Separate
    processes are isolated and were verified against real MAST.
    """
    return preprocess.download_kepler_light_curve(kepid, download_dir=download_dir)


def _group_pending_by_kepid(
    pending: list[tuple[int, pd.Series, str, Path]],
) -> dict[int, list[tuple[int, pd.Series, str, Path]]]:
    """Group live targets by host so one download serves every planet.

    KOI rows are planet candidates, not stars: several targets commonly share a
    ``kepid``. Downloading them concurrently into the same MAST folder can
    corrupt a FITS file, and downloading them sequentially wastes bandwidth.
    """
    groups: dict[int, list[tuple[int, pd.Series, str, Path]]] = {}
    for item in pending:
        try:
            kepid = int(item[1]["kepid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CacheError(
                f"target {item[2]} has no usable kepid for live download"
            ) from exc
        groups.setdefault(kepid, []).append(item)
    return groups


def _record_live_group(
    items: list[tuple[int, pd.Series, str, Path]],
    time_values: np.ndarray,
    flux_values: np.ndarray,
    *,
    n_bins: int,
    record: Callable[..., None],
) -> None:
    """Fold one downloaded light curve for every target on that host."""
    for item in items:
        try:
            flux, feature_vector = _fold_and_features(
                item[1], time_values, flux_values, n_bins=n_bins
            )
        except Exception as exc:  # noqa: BLE001 - recorded per target
            record(item, None, None, exc)
        else:
            record(item, flux, feature_vector, None)


def _fold_and_features(
    row: pd.Series,
    time_values: np.ndarray,
    flux_values: np.ndarray,
    *,
    n_bins: int,
) -> tuple[np.ndarray, np.ndarray]:
    folded = preprocess.preprocess_light_curve(
        time_values,
        flux_values,
        period=float(row["koi_period"]),
        t0=float(row["koi_time0bk"]),
        duration_hours=float(row["koi_duration"]),
        n_bins=n_bins,
        expected_depth_ppm=(
            float(row["koi_depth"]) if pd.notna(row.get("koi_depth")) else None
        ),
    )
    feature_vector = features.build_feature_vector(row.to_dict(), folded.measured)
    return folded.flux, feature_vector


def _target_arrays(
    row: pd.Series,
    *,
    mode: str,
    n_bins: int,
    seed: int,
    cache_dir: Path,
) -> tuple[np.ndarray, np.ndarray]:
    if mode == "stub":
        time_values, flux_values = stub.generate_stub_light_curve(row, seed=seed)
    elif mode == "live":
        time_values, flux_values = preprocess.download_kepler_light_curve(
            int(row["kepid"]), download_dir=cache_dir.parent / "mast"
        )
    else:  # pragma: no cover - config validation already prevents this
        raise CacheError(f"unknown data mode: {mode}")
    return _fold_and_features(row, time_values, flux_values, n_bins=n_bins)


def build_cache(
    labels: pd.DataFrame,
    *,
    mode: str,
    cache_dir: str | Path,
    n_bins: int = 400,
    seed: int = 42,
    rebuild: bool = False,
    strict: bool = True,
    workers: int = 1,
    progress: ProgressCallback | None = None,
) -> CacheBuildReport:
    """Build or extend the cache for every row in ``labels``.

    Existing entries are reused unless ``rebuild`` is set. In live mode failed
    downloads are recorded and skipped (``strict=False``); in stub mode a
    failure is a bug and raises. Live downloads may run in a bounded process
    pool (MAST is the bottleneck: ~45 s/target sequential on the dev network),
    and every target sharing a host star reuses one download.
    """
    started = time.perf_counter()
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    if labels.empty:
        raise CacheError("no labels to cache")
    for required in ("target_id", "host_star", "koi_disposition", "label"):
        if required not in labels.columns:
            raise CacheError(f"labels are missing column {required!r}")

    existing = load_manifest(cache_path)
    if existing is None:
        entries: dict[str, dict[str, Any]] = {}
        skipped: dict[str, str] = {}
    else:
        if existing.get("n_bins") != n_bins:
            raise CacheError(
                f"cache at {cache_path} was built with n_bins={existing.get('n_bins')}; "
                f"requested n_bins={n_bins}. Use a different data root."
            )
        if existing.get("mode") != mode:
            raise CacheError(
                f"cache at {cache_path} is mode={existing.get('mode')}, requested {mode}"
            )
        entries = dict(existing.get("targets", {}))
        skipped = dict(existing.get("skipped", {}))
    if rebuild:
        entries = {}

    rows = labels.sort_values("target_id").reset_index(drop=True)
    total = len(rows)
    new_count = 0
    reused_count = 0
    failed = 0
    completed = 0
    fresh: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    pending: list[tuple[int, pd.Series, str, Path]] = []
    for index, row in rows.iterrows():
        target_id = str(row["target_id"])
        npz_path = cache_path / f"{target_id}.npz"
        if not rebuild and target_id in entries and npz_path.exists():
            reused_count += 1
            completed += 1
            if progress is not None and (index % 25 == 0 or index == total - 1):
                progress(
                    {
                        "stage": "cache",
                        "done": completed,
                        "total": total,
                        "target_id": target_id,
                        "reused": True,
                    }
                )
            continue
        pending.append((int(index), row, target_id, npz_path))

    def process(item: tuple[int, pd.Series, str, Path]):
        _, row, _, _ = item
        try:
            arrays = _target_arrays(
                row, mode=mode, n_bins=n_bins, seed=seed, cache_dir=cache_path
            )
            return item, arrays[0], arrays[1], None
        except Exception as exc:  # noqa: BLE001 - recorded per target
            return item, None, None, exc

    def record(
        item: tuple[int, pd.Series, str, Path],
        flux: np.ndarray | None,
        feature_vector: np.ndarray | None,
        error: Exception | None,
    ) -> None:
        nonlocal new_count, failed, completed
        _, row, target_id, npz_path = item
        if error is not None:
            if strict:
                raise CacheError(f"failed to cache {target_id}: {error}") from error
            failed += 1
            skipped[target_id] = f"{type(error).__name__}: {error}"
            completed += 1
            if progress is not None:
                progress(
                    {
                        "stage": "cache",
                        "done": completed,
                        "total": total,
                        "target_id": target_id,
                        "skipped": True,
                    }
                )
            return

        assert flux is not None and feature_vector is not None
        _write_target_npz(npz_path, flux, feature_vector)
        entries[target_id] = {
            "path": npz_path.name,
            "content_sha1": content_sha1(flux, feature_vector),
            "host_star": str(row["host_star"]),
            "label": int(row["label"]),
            "disposition": str(row["koi_disposition"]),
        }
        skipped.pop(target_id, None)
        fresh[target_id] = (flux, feature_vector)
        new_count += 1
        completed += 1
        if progress is not None and (new_count % 10 == 0 or completed == total):
            progress(
                {
                    "stage": "cache",
                    "done": completed,
                    "total": total,
                    "target_id": target_id,
                    "reused": False,
                }
            )
        if new_count % 50 == 0:
            _write_manifest(
                cache_path,
                _manifest_payload(
                    mode=mode,
                    n_bins=n_bins,
                    entries=entries,
                    skipped=skipped,
                    created_at=existing.get("created_at") if existing else None,
                ),
            )

    bounded_workers = max(1, min(int(workers), 8))
    if mode == "live" and pending:
        groups = _group_pending_by_kepid(pending)
        mast_dir = str((cache_path.parent / "mast").resolve())
        if bounded_workers > 1 and not strict:
            with ProcessPoolExecutor(max_workers=bounded_workers) as pool:
                futures = {
                    pool.submit(_live_download_worker, kepid, mast_dir): (kepid, items)
                    for kepid, items in groups.items()
                }
                for future in as_completed(futures):
                    kepid, items = futures[future]
                    try:
                        time_values, flux_values = future.result()
                    except Exception as exc:  # noqa: BLE001 - recorded per target
                        for item in items:
                            record(item, None, None, exc)
                    else:
                        _record_live_group(
                            items,
                            time_values,
                            flux_values,
                            n_bins=n_bins,
                            record=record,
                        )
        else:
            for kepid, items in groups.items():
                try:
                    time_values, flux_values = preprocess.download_kepler_light_curve(
                        kepid, download_dir=mast_dir
                    )
                except Exception as exc:  # noqa: BLE001 - recorded per target
                    for item in items:
                        record(item, None, None, exc)
                else:
                    _record_live_group(
                        items,
                        time_values,
                        flux_values,
                        n_bins=n_bins,
                        record=record,
                    )
    else:
        for item in pending:
            record(*process(item))

    if not entries:
        raise CacheError(
            f"no targets were cached ({failed} failed); check the data mode and network"
        )

    manifest = _manifest_payload(
        mode=mode,
        n_bins=n_bins,
        entries=entries,
        skipped=skipped,
        created_at=existing.get("created_at") if existing else None,
    )
    packed = _ensure_packed(
        cache_path,
        entries,
        manifest["dataset_fingerprint"],
        fresh,
    )
    if packed is not None:
        manifest["packed"] = packed
    _write_manifest(cache_path, manifest)
    return CacheBuildReport(
        mode=mode,
        cache_dir=str(cache_path),
        processed=total,
        cached=len(entries),
        new=new_count,
        reused=reused_count,
        skipped=failed,
        dataset_fingerprint=manifest["dataset_fingerprint"],
        seconds=time.perf_counter() - started,
    )


def _manifest_payload(
    *,
    mode: str,
    n_bins: int,
    entries: dict[str, dict[str, Any]],
    skipped: dict[str, str],
    created_at: str | None,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "n_bins": n_bins,
        "feature_names": list(features.FEATURE_NAMES),
        "created_at": created_at or now,
        "updated_at": now,
        "dataset_fingerprint": dataset_fingerprint(entries, n_bins=n_bins),
        "targets": dict(sorted(entries.items())),
        "skipped": dict(sorted(skipped.items())),
    }
