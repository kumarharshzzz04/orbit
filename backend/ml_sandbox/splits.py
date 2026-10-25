"""Grouped, frozen train/validation/test splits.

Rules:
- Group by host star. A star never appears in two splits; this is the leakage
  trap the Skeptic is briefed to hunt for.
- Freeze once, to ``data/<mode>/splits/<version>.json``. Adding new targets
  after the freeze is an error: bump ``data.split_version`` deliberately.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

SPLIT_NAMES = ("train", "val", "test")
DEFAULT_FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}


class FrozenSplitError(RuntimeError):
    """Raised when a frozen split would have to change."""


@dataclass(frozen=True)
class SplitAssignment:
    by_target: dict[str, str]
    host_by_target: dict[str, str]
    fingerprint: str
    dataset_fingerprint: str
    counts: dict[str, int]
    path: Path
    version: str
    seed: int


def _fingerprint(
    assignments: dict[str, dict[str, str]],
    dataset_fingerprint: str,
    seed: int,
) -> str:
    lines = [
        f"{target_id}\t{assignments[target_id]['host']}\t{assignments[target_id]['split']}"
        for target_id in sorted(assignments)
    ]
    digest = hashlib.sha1()
    digest.update(dataset_fingerprint.encode("utf-8"))
    digest.update(f"\nseed={seed}\n".encode())
    digest.update("\n".join(lines).encode("utf-8"))
    return digest.hexdigest()


def assign_grouped_split(
    targets: pd.DataFrame,
    *,
    seed: int = 42,
    fractions: dict[str, float] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    """Assign whole host stars to splits, greedily matching target fractions."""
    fractions = fractions or DEFAULT_FRACTIONS
    if set(fractions) != set(SPLIT_NAMES):
        raise ValueError(f"fractions must define exactly {SPLIT_NAMES}")
    if abs(sum(fractions.values()) - 1.0) > 1e-9:
        raise ValueError("fractions must sum to 1.0")

    if targets["target_id"].duplicated().any():
        raise FrozenSplitError("target_id values must be unique")
    if targets["host_star"].isna().any():
        raise FrozenSplitError("every target needs a host_star")

    host_counts = targets.groupby("host_star", sort=False).size().astype(int).to_dict()
    total = int(sum(host_counts.values()))
    desired = {name: fractions[name] * total for name in SPLIT_NAMES}
    assigned = {name: 0 for name in SPLIT_NAMES}
    host_split: dict[str, str] = {}

    order = sorted(
        host_counts,
        key=lambda host: hashlib.sha1(f"{seed}:{host}".encode()).hexdigest(),
    )
    for host in order:
        deficits = {name: desired[name] - assigned[name] for name in SPLIT_NAMES}
        chosen = max(
            SPLIT_NAMES,
            key=lambda name: (deficits[name], -SPLIT_NAMES.index(name)),
        )
        host_split[str(host)] = chosen
        assigned[chosen] += int(host_counts[host])

    empty = [name for name in SPLIT_NAMES if assigned[name] == 0]
    if empty:
        raise FrozenSplitError(
            "cannot make a grouped split with non-empty "
            + ", ".join(empty)
            + f" from {len(host_counts)} host stars; cache more targets"
        )

    assignments: dict[str, dict[str, str]] = {}
    for row in targets.sort_values("target_id").itertuples(index=False):
        host = str(row.host_star)
        assignments[str(row.target_id)] = {"host": host, "split": host_split[host]}

    _assert_no_leakage(assignments)
    return assignments, assigned


def _assert_no_leakage(assignments: dict[str, dict[str, str]]) -> None:
    host_to_split: dict[str, str] = {}
    for target_id, entry in assignments.items():
        host = entry["host"]
        split = entry["split"]
        if split not in SPLIT_NAMES:
            raise FrozenSplitError(f"invalid split {split!r} for {target_id}")
        previous = host_to_split.setdefault(host, split)
        if previous != split:
            raise FrozenSplitError(
                f"LEAKAGE: host {host} appears in {previous} and {split}"
            )


def _split_path(splits_dir: str | Path, version: str) -> Path:
    return Path(splits_dir) / f"{version}.json"


def freeze_split(
    targets: pd.DataFrame,
    *,
    dataset_fingerprint: str,
    splits_dir: str | Path,
    version: str = "v1",
    seed: int = 42,
    fractions: dict[str, float] | None = None,
) -> SplitAssignment:
    """Load the frozen split for this dataset, or create it exactly once."""
    if targets.empty:
        raise FrozenSplitError("cannot split an empty dataset")
    if not dataset_fingerprint:
        raise FrozenSplitError("dataset fingerprint is required to freeze a split")

    path = _split_path(splits_dir, version)
    requested = set(targets["target_id"].astype(str))

    if path.exists():
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FrozenSplitError(f"split file is not valid JSON: {path}") from exc

        if manifest.get("version") != version:
            raise FrozenSplitError(f"split file version mismatch at {path}")
        if manifest.get("dataset_fingerprint") != dataset_fingerprint:
            raise FrozenSplitError(
                f"split {version} at {path} was frozen for dataset "
                f"{str(manifest.get('dataset_fingerprint'))[:12]}, but the cache is "
                f"{dataset_fingerprint[:12]}. The split is frozen; use a new "
                "data.split_version (e.g. v2) for a different dataset."
            )

        assignments = manifest.get("assignments", {})
        if not isinstance(assignments, dict) or not assignments:
            raise FrozenSplitError(f"split file is empty or malformed: {path}")
        frozen = set(assignments)
        missing = sorted(requested - frozen)
        removed = sorted(frozen - requested)
        if missing or removed:
            details = []
            if missing:
                details.append(f"{len(missing)} new target(s), e.g. {missing[0]}")
            if removed:
                details.append(
                    f"{len(removed)} cached target(s) missing, e.g. {removed[0]}"
                )
            raise FrozenSplitError(
                f"split {version} is frozen and cannot change: "
                + "; ".join(details)
                + ". Rebuild the full cache first, or bump data.split_version."
            )

        expected = _fingerprint(assignments, dataset_fingerprint, int(manifest["seed"]))
        if manifest.get("fingerprint") != expected:
            raise FrozenSplitError(
                f"split fingerprint mismatch at {path}: the file was edited"
            )
        by_target = {target_id: assignments[target_id]["split"] for target_id in frozen}
        host_by_target = {
            target_id: assignments[target_id]["host"] for target_id in frozen
        }
        counts = {name: 0 for name in SPLIT_NAMES}
        for split in by_target.values():
            counts[split] += 1
        return SplitAssignment(
            by_target=by_target,
            host_by_target=host_by_target,
            fingerprint=manifest["fingerprint"],
            dataset_fingerprint=dataset_fingerprint,
            counts=counts,
            path=path,
            version=version,
            seed=int(manifest["seed"]),
        )

    assignments, counts = assign_grouped_split(targets, seed=seed, fractions=fractions)
    fingerprint = _fingerprint(assignments, dataset_fingerprint, seed)
    label_by_target = dict(
        zip(
            targets["target_id"].astype(str),
            targets["label"].astype(int),
            strict=False,
        )
    )
    payload: dict[str, Any] = {
        "version": version,
        "seed": seed,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_fingerprint": dataset_fingerprint,
        "fingerprint": fingerprint,
        "counts": counts,
        "label_counts": {
            split: int(
                sum(
                    1
                    for target_id, entry in assignments.items()
                    if entry["split"] == split and label_by_target[target_id]
                )
            )
            for split in SPLIT_NAMES
        },
        "assignments": assignments,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)

    by_target = {
        target_id: assignments[target_id]["split"] for target_id in assignments
    }
    host_by_target = {
        target_id: assignments[target_id]["host"] for target_id in assignments
    }
    return SplitAssignment(
        by_target=by_target,
        host_by_target=host_by_target,
        fingerprint=fingerprint,
        dataset_fingerprint=dataset_fingerprint,
        counts={name: int(counts[name]) for name in SPLIT_NAMES},
        path=path,
        version=version,
        seed=seed,
    )
