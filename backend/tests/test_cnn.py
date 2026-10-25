from __future__ import annotations

import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from support import make_config, write_config  # noqa: E402

from ml_sandbox import dataset, train  # noqa: E402
from ml_sandbox.config import RunConfig  # noqa: E402
from ml_sandbox.evaluate import METRIC_NAMES  # noqa: E402
from ml_sandbox.models.cnn import (  # noqa: E402
    TransitCNN,
    cnn_input,
    load_cnn,
    predict_probabilities,
)


@pytest.mark.cnn
def test_cnn_input_transform() -> None:
    flux = np.array([[0.99, 1.0, 1.01]], dtype=np.float32)
    scaled = cnn_input(flux)
    assert scaled[0, 0] == pytest.approx(-1.0)
    assert scaled[0, 1] == pytest.approx(0.0)
    assert scaled[0, 2] == pytest.approx(1.0)
    extreme = cnn_input(np.array([[0.0, 2.0]], dtype=np.float32))
    assert extreme.min() == pytest.approx(-5.0)
    assert extreme.max() == pytest.approx(5.0)


@pytest.mark.cnn
def test_cnn_initialization_is_seeded() -> None:
    torch.manual_seed(3)
    first = TransitCNN(channels=[8, 8, 8], kernel_size=3, fc_dim=8)
    torch.manual_seed(3)
    second = TransitCNN(channels=[8, 8, 8], kernel_size=3, fc_dim=8)
    first.eval()
    second.eval()
    inputs = torch.zeros(2, 1, 400)
    assert torch.equal(first(inputs), second(inputs))


@pytest.mark.cnn
def test_cnn_training_is_replayable(tmp_path, stub_root) -> None:
    raw = make_config(
        stub_root,
        model="cnn",
        name="cnn-replay",
        training={
            "max_epochs": 1,
            "batch_size": 64,
            "num_threads": 1,
            "patience": 1,
            "max_train_seconds": 120.0,
        },
    )
    config_path = write_config(tmp_path / "cnn.json", raw)

    first = train.run(config_path, tmp_path / "cnn-1")
    second = train.run(config_path, tmp_path / "cnn-2")
    assert first["ok"] is True and second["ok"] is True
    for name in METRIC_NAMES:
        assert first["metrics"][name] == pytest.approx(
            second["metrics"][name], abs=1e-9
        ), name
    assert first["dataset_fingerprint"] == second["dataset_fingerprint"]
    assert first["split_fingerprint"] == second["split_fingerprint"]

    record = json.loads((tmp_path / "cnn-1" / "run_record.json").read_text())
    assert record["model_family"] == "cnn"
    assert record["training"]["epochs_run"] == 1
    assert (tmp_path / "cnn-1" / "model.pt").exists()

    model, checkpoint = load_cnn(tmp_path / "cnn-1" / "model.pt")
    assert checkpoint["n_bins"] == 400
    loaded = dataset.load_dataset(RunConfig.from_dict(raw))
    test_split = loaded.select("test")
    probabilities = predict_probabilities(model, test_split.flux)
    assert probabilities.shape == (test_split.size,)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)
