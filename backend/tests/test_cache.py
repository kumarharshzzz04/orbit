from __future__ import annotations

import json

import numpy as np
import pytest
from support import make_config

from ml_sandbox import cache, dataset, stub
from ml_sandbox.config import RunConfig


def build(root, n_targets: int = 50, seed: int = 3):
    frame = stub.make_stub_labels(n_targets=n_targets, seed=seed)
    return cache.build_cache(
        frame,
        mode="stub",
        cache_dir=root / "cache",
        n_bins=400,
        seed=seed,
    )


def test_cache_is_deterministic_across_roots(tmp_path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = build(first_root)
    second = build(second_root)
    assert first.dataset_fingerprint == second.dataset_fingerprint
    assert first.new == second.new == 50

    target_id = sorted(
        json.loads((first_root / "cache" / "manifest.json").read_text())["targets"]
    )[0]
    flux_a, features_a = cache.read_target_npz(
        first_root / "cache" / f"{target_id}.npz"
    )
    flux_b, features_b = cache.read_target_npz(
        second_root / "cache" / f"{target_id}.npz"
    )
    np.testing.assert_array_equal(flux_a, flux_b)
    np.testing.assert_array_equal(features_a, features_b)


def test_different_seed_changes_the_fingerprint(tmp_path) -> None:
    first = build(tmp_path / "a", seed=3)
    second = build(tmp_path / "b", seed=4)
    assert first.dataset_fingerprint != second.dataset_fingerprint


def test_rebuild_reuses_existing_targets(tmp_path) -> None:
    root = tmp_path / "data"
    first = build(root)
    second = build(root)
    assert second.reused == first.new
    assert second.new == 0
    assert second.dataset_fingerprint == first.dataset_fingerprint


def test_n_bins_change_is_refused(tmp_path) -> None:
    root = tmp_path / "data"
    build(root)
    frame = stub.make_stub_labels(n_targets=50, seed=3)
    with pytest.raises(cache.CacheError, match="n_bins"):
        cache.build_cache(
            frame,
            mode="stub",
            cache_dir=root / "cache",
            n_bins=200,
            seed=3,
        )


def test_tampered_arrays_are_caught(tmp_path) -> None:
    root = tmp_path / "data"
    report = build(root)
    manifest = json.loads((root / "cache" / "manifest.json").read_text())
    target_id = sorted(manifest["targets"])[0]
    path = root / "cache" / f"{target_id}.npz"
    with np.load(path) as data:
        flux = np.asarray(data["flux"]).copy()
        features = np.asarray(data["features"]).copy()
    flux[200] += 0.01
    np.savez(
        path,
        flux=flux,
        features=features,
        feature_names=np.asarray(manifest["feature_names"]),
    )
    (root / "cache" / cache.PACKED_NAME).unlink()

    raw = make_config(
        root,
        data={
            "stub_targets": 50,
            "stub_seed": 3,
            "expected_dataset_fingerprint": report.dataset_fingerprint,
        },
    )
    with pytest.raises(dataset.DatasetError, match="do not match"):
        dataset.load_dataset(RunConfig.from_dict(raw))


def test_live_build_with_fake_arrays_records_all_targets(tmp_path, monkeypatch) -> None:
    frame = stub.make_stub_labels(n_targets=20, seed=5)

    def fake_target_arrays(row, *, mode, n_bins, seed, cache_dir):
        assert mode == "live"
        return (
            np.full(n_bins, 0.999, dtype=np.float32),
            np.arange(14, dtype=np.float32),
        )

    monkeypatch.setattr(cache, "_target_arrays", fake_target_arrays)
    report = cache.build_cache(
        frame,
        mode="live",
        cache_dir=tmp_path / "cache",
        seed=5,
        strict=False,
        workers=1,
    )
    assert report.new == 20
    assert report.skipped == 0
    assert report.cached == 20
    manifest = json.loads((tmp_path / "cache" / "manifest.json").read_text())
    assert manifest["mode"] == "live"
    assert len(manifest["targets"]) == 20
    assert manifest["packed"]["n_targets"] == 20


def test_tampered_packed_matrix_is_caught(tmp_path) -> None:
    root = tmp_path / "data"
    report = build(root)
    packed_path = root / "cache" / cache.PACKED_NAME
    with np.load(packed_path) as data:
        payload = {name: np.asarray(data[name]).copy() for name in data.files}
    payload["flux"][0, 0] += 0.01
    np.savez(packed_path, **payload)

    raw = make_config(
        root,
        data={
            "stub_targets": 50,
            "stub_seed": 3,
            "expected_dataset_fingerprint": report.dataset_fingerprint,
        },
    )
    with pytest.raises(dataset.DatasetError, match="packed cache content hash"):
        dataset.load_dataset(RunConfig.from_dict(raw))


def test_missing_cache_has_actionable_error(tmp_path) -> None:
    raw = make_config(tmp_path / "empty", data={"stub_targets": 50})
    with pytest.raises(dataset.DatasetError, match="build_cache"):
        dataset.load_dataset(RunConfig.from_dict(raw))
