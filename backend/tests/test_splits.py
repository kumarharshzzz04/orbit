from __future__ import annotations

import json

import pandas as pd
import pytest

from ml_sandbox import splits
from ml_sandbox.splits import FrozenSplitError


def make_targets(n_hosts: int = 20, per_host: int = 3) -> pd.DataFrame:
    rows = []
    for host in range(n_hosts):
        for planet in range(per_host):
            rows.append(
                {
                    "target_id": f"K{host:05d}.{planet + 1:02d}",
                    "host_star": str(1_000_000 + host),
                    "label": int((host + planet) % 2 == 0),
                }
            )
    return pd.DataFrame(rows)


def test_split_is_grouped_and_frozen(tmp_path) -> None:
    targets = make_targets()
    fingerprint = "a" * 40
    first = splits.freeze_split(
        targets,
        dataset_fingerprint=fingerprint,
        splits_dir=tmp_path,
        version="v1",
        seed=42,
    )
    second = splits.freeze_split(
        targets,
        dataset_fingerprint=fingerprint,
        splits_dir=tmp_path,
        version="v1",
        seed=42,
    )
    assert first.fingerprint == second.fingerprint
    assert first.counts == second.counts
    assert sum(first.counts.values()) == len(targets)
    assert set(first.by_target.values()) == {"train", "val", "test"}

    for name, expected in (("train", 0.70), ("val", 0.15), ("test", 0.15)):
        share = first.counts[name] / len(targets)
        assert abs(share - expected) < 0.10

    by_host: dict[str, set[str]] = {}
    for row in targets.itertuples(index=False):
        by_host.setdefault(str(row.host_star), set()).add(
            first.by_target[row.target_id]
        )
    assert all(len(names) == 1 for names in by_host.values())

    assert (tmp_path / "v1.json").exists()


def test_freezing_refuses_new_targets(tmp_path) -> None:
    targets = make_targets()
    fingerprint = "b" * 40
    splits.freeze_split(
        targets,
        dataset_fingerprint=fingerprint,
        splits_dir=tmp_path,
        seed=42,
    )
    extra = pd.concat(
        [
            targets,
            pd.DataFrame(
                [
                    {
                        "target_id": "K99999.01",
                        "host_star": "9999999",
                        "label": 1,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(FrozenSplitError, match="frozen"):
        splits.freeze_split(
            extra,
            dataset_fingerprint=fingerprint,
            splits_dir=tmp_path,
            seed=42,
        )


def test_freezing_refuses_a_different_dataset(tmp_path) -> None:
    targets = make_targets()
    splits.freeze_split(
        targets,
        dataset_fingerprint="c" * 40,
        splits_dir=tmp_path,
        seed=42,
    )
    with pytest.raises(FrozenSplitError, match="frozen for dataset"):
        splits.freeze_split(
            targets,
            dataset_fingerprint="d" * 40,
            splits_dir=tmp_path,
            seed=42,
        )


def test_hand_edited_split_is_rejected(tmp_path) -> None:
    targets = make_targets()
    fingerprint = "e" * 40
    splits.freeze_split(
        targets,
        dataset_fingerprint=fingerprint,
        splits_dir=tmp_path,
        seed=42,
    )
    path = tmp_path / "v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    victim = sorted(manifest["assignments"])[0]
    manifest["assignments"][victim]["split"] = "test"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(FrozenSplitError):
        splits.freeze_split(
            targets,
            dataset_fingerprint=fingerprint,
            splits_dir=tmp_path,
            seed=42,
        )


def test_same_seed_reproduces_assignments(tmp_path) -> None:
    targets = make_targets()
    first = splits.freeze_split(
        targets,
        dataset_fingerprint="f" * 40,
        splits_dir=tmp_path / "a",
        seed=42,
    )
    second = splits.freeze_split(
        targets,
        dataset_fingerprint="f" * 40,
        splits_dir=tmp_path / "b",
        seed=42,
    )
    assert first.by_target == second.by_target
    assert first.fingerprint == second.fingerprint


def test_single_host_cannot_be_split(tmp_path) -> None:
    targets = make_targets(n_hosts=1, per_host=5)
    with pytest.raises(FrozenSplitError, match="host stars"):
        splits.freeze_split(
            targets,
            dataset_fingerprint="1" * 40,
            splits_dir=tmp_path,
            seed=42,
        )
