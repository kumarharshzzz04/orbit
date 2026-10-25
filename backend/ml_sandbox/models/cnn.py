"""orbit-cnn-v1: a small 1D CNN over the 400-bin folded flux vector.

The architecture follows docs/ML.md: Conv1D(32) - pool - Conv1D(64) - pool -
Conv1D(96) - global pool - dropout - FC(64) - one logit. Logits are used during
training with BCEWithLogitsLoss; inference applies sigmoid.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn

from ..config import RunConfig
from ..dataset import DatasetSplit
from .base import ModelResult

INPUT_DESCRIPTION = "((pdcsap_flux - 1.0) * 100).clip(-5, 5)"


class TransitCNN(nn.Module):
    def __init__(
        self,
        *,
        channels: tuple[int, int, int] | list[int] = (32, 64, 96),
        kernel_size: int = 7,
        dropout: float = 0.3,
        fc_dim: int = 64,
    ) -> None:
        super().__init__()
        first, second, third = (int(channel) for channel in channels)
        padding = kernel_size // 2
        self.features = nn.Sequential(
            nn.Conv1d(1, first, kernel_size, padding=padding),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(first, second, kernel_size, padding=padding),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(second, third, kernel_size, padding=padding),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(third, fc_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_dim, 1),
        )

    def forward(self, flux: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(flux)).squeeze(1)


def cnn_input(flux: np.ndarray) -> np.ndarray:
    """Fixed input transform, shared by training and inference."""
    scaled = (np.asarray(flux, dtype=np.float32) - 1.0) * 100.0
    return np.clip(scaled, -5.0, 5.0)


def _predict(
    model: nn.Module,
    scaled_flux: np.ndarray,
    *,
    batch_size: int = 256,
) -> np.ndarray:
    model.eval()
    device = next(model.parameters()).device
    probabilities: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(scaled_flux), batch_size):
            batch = torch.as_tensor(
                scaled_flux[start : start + batch_size][:, None, :],
                dtype=torch.float32,
            ).to(device)
            logits = model(batch)
            probabilities.append(torch.sigmoid(logits).cpu().numpy())
    if not probabilities:
        return np.empty(0, dtype=np.float64)
    return np.concatenate(probabilities).astype(np.float64)


def _augment(
    batch: np.ndarray,
    rng: np.random.Generator,
    *,
    phase_shift: bool,
    noise_ppm: float,
) -> np.ndarray:
    augmented = batch.copy()
    if phase_shift:
        for index in range(augmented.shape[0]):
            shift = int(rng.integers(0, augmented.shape[1]))
            augmented[index] = np.roll(augmented[index], shift)
    if noise_ppm > 0:
        # scaled input = (flux - 1) * 100, and flux noise is ppm * 1e-6.
        augmented += rng.normal(0.0, noise_ppm * 1e-4, size=augmented.shape)
    return augmented


def _pos_weight(labels: np.ndarray, class_weight: object) -> float:
    if class_weight is None:
        return 1.0
    if class_weight == "balanced":
        positives = max(int(np.sum(labels == 1)), 1)
        negatives = max(int(np.sum(labels == 0)), 1)
        return float(negatives / positives)
    return float(class_weight)


def _best_state(model: nn.Module) -> dict[str, torch.Tensor]:
    return {key: value.detach().clone() for key, value in model.state_dict().items()}


def fit_predict(
    train: DatasetSplit,
    validation: DatasetSplit,
    test: DatasetSplit,
    *,
    cfg: RunConfig,
    out_dir: str | Path,
) -> ModelResult:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    params = cfg.model_params
    training = cfg.training
    seed = cfg.seed
    device_name = str(training.get("device", "cpu"))
    if device_name == "cuda":
        # cuBLAS needs this for deterministic kernels on CUDA >= 10.2. Set before
        # any GPU work so the workspace is honoured.
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.set_num_threads(int(training["num_threads"]))
    try:
        # warn_only on GPU: some CUDA kernels have no deterministic equivalent,
        # and a hard failure would make the GPU path unusable. GPU runs are
        # recorded as such and are not claimed to be bit-reproducible.
        torch.use_deterministic_algorithms(True, warn_only=(device_name == "cuda"))
    except (RuntimeError, TypeError):
        # Older torch builds do not know every deterministic kernel; the seed
        # and single-thread setting still keep CPU runs stable.
        pass

    if device_name not in {"cpu", "cuda"}:
        raise ValueError(f"training.device must be 'cpu' or 'cuda', got {device_name!r}")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("training.device='cuda' but torch.cuda.is_available() is False")
    device = torch.device(device_name)
    if device_name == "cuda":
        torch.cuda.manual_seed_all(seed)

    architecture = {
        "channels": [int(value) for value in params["channels"]],
        "kernel_size": int(params["kernel_size"]),
        "dropout": float(params["dropout"]),
        "fc_dim": int(params["fc_dim"]),
    }
    model = TransitCNN(**architecture).to(device)
    n_params = int(sum(parameter.numel() for parameter in model.parameters()))

    x_train = cnn_input(train.flux)
    y_train = train.labels.astype(np.float32)
    x_val = cnn_input(validation.flux)
    y_val = validation.labels.astype(np.int64)
    x_test = cnn_input(test.flux)

    pos_weight = _pos_weight(train.labels, params.get("class_weight"))
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )

    batch_size = int(training["batch_size"])
    max_epochs = int(training["max_epochs"])
    patience = int(training["patience"])
    time_budget = float(training["max_train_seconds"])
    augmentation = training["augmentation"]
    phase_shift = bool(augmentation["phase_shift"])
    noise_ppm = float(augmentation["noise_ppm"])

    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    best_f1 = -1.0
    best_epoch = 0
    best_state: dict[str, torch.Tensor] | None = None
    epochs_without_improvement = 0
    epochs_run = 0
    stop_reason = "max_epochs"
    val_f1 = 0.0

    for epoch in range(1, max_epochs + 1):
        if (time.perf_counter() - started) > time_budget:
            stop_reason = "time_budget"
            break

        model.train()
        order = rng.permutation(len(x_train))
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            batch = _augment(
                x_train[indices],
                rng,
                phase_shift=phase_shift,
                noise_ppm=noise_ppm,
            )
            inputs = torch.as_tensor(
                batch[:, None, :], dtype=torch.float32, device=device
            )
            targets = torch.as_tensor(
                y_train[indices], dtype=torch.float32, device=device
            )
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()

        epochs_run = epoch
        val_probabilities = _predict(model, x_val)
        val_f1 = float(
            f1_score(
                y_val,
                (val_probabilities >= 0.5).astype(np.int64),
                zero_division=0,
            )
        )
        if val_f1 > best_f1 + 1e-6:
            best_f1 = val_f1
            best_epoch = epoch
            best_state = _best_state(model)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                stop_reason = "early_stopping"
                break

    if best_state is None:
        raise RuntimeError("CNN training finished without a usable epoch")
    model.load_state_dict(best_state)
    model.eval()

    seconds = time.perf_counter() - started
    train_probabilities = _predict(model, x_train)
    val_probabilities = _predict(model, x_val)
    test_probabilities = _predict(model, x_test)

    artifact_file = "model.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "architecture": architecture,
            "n_bins": int(train.flux.shape[1]),
            "input": INPUT_DESCRIPTION,
            "seed": seed,
        },
        out_path / artifact_file,
    )

    return ModelResult(
        val_probabilities=val_probabilities,
        test_probabilities=test_probabilities,
        train_probabilities=train_probabilities,
        artifact_file=artifact_file,
        training={
            "model_family": "cnn",
            "train_seconds": round(seconds, 4),
            "n_params": n_params,
            "epochs_run": epochs_run,
            "best_epoch": best_epoch,
            "best_val_f1_at_0_5": round(best_f1, 6),
            "last_val_f1_at_0_5": round(val_f1, 6),
            "stop_reason": stop_reason,
            "pos_weight": pos_weight,
            "augmentation": dict(augmentation),
            "params": architecture,
            "input": INPUT_DESCRIPTION,
        },
    )


def load_cnn(path: str | Path) -> tuple[TransitCNN, dict]:
    """Load a saved checkpoint for inference (used by tests and future APIs)."""
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:  # pragma: no cover - torch < 2.0
        checkpoint = torch.load(path, map_location="cpu")
    architecture = checkpoint["architecture"]
    model = TransitCNN(**architecture)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model, checkpoint


def predict_probabilities(
    model: TransitCNN,
    flux: np.ndarray,
    *,
    batch_size: int = 256,
) -> np.ndarray:
    return _predict(model, cnn_input(flux), batch_size=batch_size)
