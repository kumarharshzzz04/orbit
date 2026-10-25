from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
for entry in (str(BACKEND_DIR), str(TEST_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from support import N_TARGETS, STUB_SEED  # noqa: E402

from ml_sandbox import cache, stub  # noqa: E402


@pytest.fixture(scope="session")
def stub_dataset(tmp_path_factory: pytest.TempPathFactory) -> dict:
    root = tmp_path_factory.mktemp("orbit-stub-data")
    frame = stub.make_stub_labels(n_targets=N_TARGETS, seed=STUB_SEED)
    report = cache.build_cache(
        frame,
        mode="stub",
        cache_dir=root / "cache",
        n_bins=400,
        seed=STUB_SEED,
    )
    return {"root": root, "report": report}


@pytest.fixture(scope="session")
def stub_root(stub_dataset: dict) -> Path:
    return stub_dataset["root"]


@pytest.fixture()
def config_writer(tmp_path: Path, stub_root: Path):
    counter = {"value": 0}

    def _write(model: str = "baseline", name: str | None = None, **overrides):
        from support import make_config, write_config

        counter["value"] += 1
        run_name = name or f"test-run-{counter['value']}"
        raw = make_config(stub_root, model=model, name=run_name, **overrides)
        path = tmp_path / f"config_{counter['value']}.json"
        return write_config(path, raw)

    return _write
