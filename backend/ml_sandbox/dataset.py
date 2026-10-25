"""Materialize the verified cache into model-ready arrays."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import cache, features, splits
from .config import RunConfig


class DatasetError(RuntimeError):
    """Raised when the cache cannot satisfy a run config."""


@dataclass
class DatasetSplit:
    name: str
    target_ids: np.ndarray
    hosts: np.ndarray
    labels: np.ndarray
    dispositions: np.ndarray
    flux: np.ndarray
    feature_matrix: np.ndarray

    @property
    def size(self) -> int:
        return int(self.labels.size)


@dataclass
class OrbitDataset:
    target_ids: np.ndarray
    hosts: np.ndarray
    labels: np.ndarray
    dispositions: np.ndarray
    split_names: np.ndarray
    flux: np.ndarray
    all_features: np.ndarray
    feature_matrix: np.ndarray
    feature_names: list[str]
    dataset_fingerprint: str
    split_fingerprint: str
    split_counts: dict[str, int]
    split_path: str
    n_bins: int

    def indices_for_split(self, name: str) -> np.ndarray:
        return np.flatnonzero(self.split_names == name)

    def select(self, name: str) -> DatasetSplit:
        indices = self.indices_for_split(name)
        return DatasetSplit(
            name=name,
            target_ids=self.target_ids[indices],
            hosts=self.hosts[indices],
            labels=self.labels[indices],
            dispositions=self.dispositions[indices],
            flux=self.flux[indices],
            feature_matrix=self.feature_matrix[indices],
        )

    @property
    def split_sizes(self) -> dict[str, int]:
        return {
            name: int(np.sum(self.split_names == name)) for name in splits.SPLIT_NAMES
        }


def _read_entries(
    cache_dir: Path,
    entries: dict[str, dict],
    *,
    n_bins: int,
    verify_content: bool,
) -> tuple[
    list[str], list[str], list[int], list[str], list[np.ndarray], list[np.ndarray]
]:
    ids: list[str] = []
    hosts: list[str] = []
    labels: list[int] = []
    dispositions: list[str] = []
    flux_rows: list[np.ndarray] = []
    feature_rows: list[np.ndarray] = []

    for target_id in sorted(entries):
        entry = entries[target_id]
        path = cache_dir / entry["path"]
        if not path.exists():
            raise DatasetError(f"cached target file is missing: {path}")
        flux, feature_vector = cache.read_target_npz(path)
        if flux.shape != (n_bins,):
            raise DatasetError(
                f"{target_id}: flux shape {flux.shape}, expected ({n_bins},)"
            )
        if feature_vector.shape != (len(features.FEATURE_NAMES),):
            raise DatasetError(
                f"{target_id}: feature shape {feature_vector.shape}, expected "
                f"({len(features.FEATURE_NAMES)},)"
            )
        if verify_content:
            actual = cache.content_sha1(flux, feature_vector)
            if actual != entry.get("content_sha1"):
                raise DatasetError(
                    f"{target_id}: cached arrays do not match the manifest hash "
                    f"({actual[:12]} != {str(entry.get('content_sha1'))[:12]}); "
                    "rebuild the cache"
                )
        ids.append(target_id)
        hosts.append(str(entry["host_star"]))
        labels.append(int(entry["label"]))
        dispositions.append(str(entry["disposition"]))
        flux_rows.append(flux)
        feature_rows.append(feature_vector)

    if not ids:
        raise DatasetError("cache has no targets")
    return ids, hosts, labels, dispositions, flux_rows, feature_rows


def _read_packed_entries(
    entries: dict[str, dict],
    packed: tuple[list[str], np.ndarray, np.ndarray],
) -> tuple[list[str], list[str], list[int], list[str], np.ndarray, np.ndarray]:
    """Align the verified packed matrix with manifest metadata."""
    packed_ids, flux_matrix, feature_matrix = packed
    index_by_id = {target_id: index for index, target_id in enumerate(packed_ids)}
    if set(index_by_id) != set(entries):
        raise DatasetError("packed cache ids do not match the manifest")
    ids = sorted(entries)
    order = np.asarray([index_by_id[target_id] for target_id in ids], dtype=np.int64)
    return (
        ids,
        [str(entries[target_id]["host_star"]) for target_id in ids],
        [int(entries[target_id]["label"]) for target_id in ids],
        [str(entries[target_id]["disposition"]) for target_id in ids],
        np.ascontiguousarray(flux_matrix[order], dtype=np.float32),
        np.ascontiguousarray(feature_matrix[order], dtype=np.float32),
    )


def load_dataset(cfg: RunConfig) -> OrbitDataset:
    """Load, verify and split the cache described by ``cfg``."""
    cache_dir = cfg.cache_dir
    manifest = cache.load_manifest(cache_dir)
    if manifest is None:
        raise DatasetError(
            f"no cache manifest at {cache.manifest_path(cache_dir)}. "
            f"Run: python -m ml_sandbox.build_cache --mode {cfg.mode} "
            f"--targets {cfg.stub_targets}"
        )

    if manifest.get("mode") != cfg.mode:
        raise DatasetError(
            f"cache mode is {manifest.get('mode')}, config asks for {cfg.mode}"
        )
    if manifest.get("n_bins") != cfg.n_bins:
        raise DatasetError(
            f"cache n_bins is {manifest.get('n_bins')}, config asks for {cfg.n_bins}"
        )
    if list(manifest.get("feature_names", [])) != features.FEATURE_NAMES:
        raise DatasetError(
            "cache feature schema does not match this code; rebuild the cache"
        )

    entries = manifest.get("targets", {})
    recomputed = cache.dataset_fingerprint(entries, n_bins=cfg.n_bins)
    dataset_fingerprint = str(manifest.get("dataset_fingerprint", ""))
    if recomputed != dataset_fingerprint:
        raise DatasetError(
            "cache manifest fingerprint does not match its entries; "
            "the manifest was edited or a target was added without a rebuild"
        )
    expected = cfg.expected_dataset_fingerprint
    if expected and expected != dataset_fingerprint:
        raise DatasetError(
            f"dataset fingerprint mismatch: config expects {expected[:12]}, "
            f"cache is {dataset_fingerprint[:12]}. Re-run the champion and "
            "challenger on the same dataset."
        )

    try:
        packed = cache.read_packed(cache_dir, manifest)
    except cache.CacheError as exc:
        raise DatasetError(str(exc)) from exc
    if packed is not None:
        ids, hosts, labels, dispositions, flux_array, all_features = (
            _read_packed_entries(entries, packed)
        )
    else:
        ids, hosts, labels, dispositions, flux_rows, feature_rows = _read_entries(
            cache_dir,
            entries,
            n_bins=cfg.n_bins,
            verify_content=cfg.verify_content,
        )
        flux_array = np.vstack(flux_rows).astype(np.float32)
        all_features = np.vstack(feature_rows).astype(np.float32)

    targets = pd.DataFrame(
        {
            "target_id": ids,
            "host_star": hosts,
            "label": labels,
            "koi_disposition": dispositions,
        }
    )
    assignment = splits.freeze_split(
        targets,
        dataset_fingerprint=dataset_fingerprint,
        splits_dir=cfg.splits_dir,
        version=cfg.split_version,
        seed=cfg.seed,
    )

    split_names = np.asarray(
        [assignment.by_target[target_id] for target_id in ids], dtype=object
    )
    selected = features.indices_for(cfg.feature_set)
    feature_matrix = all_features[:, selected]

    return OrbitDataset(
        target_ids=np.asarray(ids, dtype=object),
        hosts=np.asarray(hosts, dtype=object),
        labels=np.asarray(labels, dtype=np.int64),
        dispositions=np.asarray(dispositions, dtype=object),
        split_names=split_names,
        flux=flux_array,
        all_features=all_features,
        feature_matrix=feature_matrix,
        feature_names=list(features.FEATURE_SETS[cfg.feature_set]),
        dataset_fingerprint=dataset_fingerprint,
        split_fingerprint=assignment.fingerprint,
        split_counts=assignment.counts,
        split_path=str(assignment.path),
        n_bins=cfg.n_bins,
    )


def write_json(path: str | Path, payload: object) -> None:
    """Small helper so every artifact is written with the same formatting."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _json_default(value: object) -> object:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")
