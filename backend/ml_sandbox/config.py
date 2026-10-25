"""Experiment configuration: validation, defaults and stable config hashing.

A run config is the unit of reproducibility. The config hash covers every value
the training code reads, so two runs with the same hash and the same dataset
fingerprint must produce the same metrics (given the same code commit).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import features as feature_sets
from . import paths

MODELS = ("baseline", "cnn")
DATA_MODES = ("stub", "live")
THRESHOLD_SELECTIONS = ("val_f1", "fixed")

_TOP_LEVEL_KEYS = {
    "name",
    "model",
    "seed",
    "hypothesis_id",
    "data",
    "features",
    "model_params",
    "training",
    "notes",
}
_DATA_KEYS = {
    "mode",
    "root",
    "n_bins",
    "split_version",
    "expected_dataset_fingerprint",
    "stub_targets",
    "stub_seed",
    "verify_content",
}
_MODEL_KEYS = {
    "baseline": {
        "n_estimators",
        "max_depth",
        "learning_rate",
        "subsample",
        "min_samples_leaf",
        "max_features",
        "class_weight",
    },
    "cnn": {
        "channels",
        "kernel_size",
        "dropout",
        "fc_dim",
        "class_weight",
    },
}
_TRAINING_COMMON = {"threshold_selection", "threshold", "max_train_seconds"}
_TRAINING_KEYS = {
    "baseline": set(_TRAINING_COMMON),
    "cnn": _TRAINING_COMMON
    | {
        "max_epochs",
        "batch_size",
        "learning_rate",
        "weight_decay",
        "patience",
        "num_threads",
        "augmentation",
    },
}

_BASELINE_DEFAULTS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.9,
    "min_samples_leaf": 4,
    "max_features": None,
    "class_weight": None,
}
_CNN_DEFAULTS: dict[str, Any] = {
    "channels": [32, 64, 96],
    "kernel_size": 7,
    "dropout": 0.3,
    "fc_dim": 64,
    "class_weight": None,
}
_TRAINING_DEFAULTS: dict[str, dict[str, Any]] = {
    "baseline": {
        "threshold_selection": "val_f1",
        "threshold": 0.5,
        "max_train_seconds": 600.0,
    },
    "cnn": {
        "threshold_selection": "val_f1",
        "threshold": 0.5,
        "max_train_seconds": 600.0,
        "max_epochs": 30,
        "batch_size": 64,
        "learning_rate": 0.001,
        "weight_decay": 0.0001,
        "patience": 6,
        "num_threads": 4,
        "augmentation": {"phase_shift": False, "noise_ppm": 0.0},
    },
}
_DATA_DEFAULTS: dict[str, Any] = {
    "mode": "stub",
    "root": None,
    "n_bins": 400,
    "split_version": "v1",
    "expected_dataset_fingerprint": None,
    "stub_targets": 1500,
    "stub_seed": 42,
    "verify_content": True,
}


class ConfigError(ValueError):
    """Raised when a run config is malformed or unsupported."""


def _fail(message: str) -> None:
    raise ConfigError(message)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{name} must be a JSON object")
    return copy.deepcopy(value)


def _unknown_keys(mapping: dict[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        _fail(f"{name} has unsupported key(s): {', '.join(unknown)}")


def _string(value: Any, name: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a non-empty string")
    return value


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        _fail(f"{name} must be >= {minimum}")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{name} must be true or false")
    return value


def _number(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_inclusive: bool = True,
    maximum_inclusive: bool = True,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        _fail(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        _fail(f"{name} must be finite")
    if minimum is not None:
        if minimum_inclusive and number < minimum:
            _fail(f"{name} must be >= {minimum}")
        if not minimum_inclusive and number <= minimum:
            _fail(f"{name} must be > {minimum}")
    if maximum is not None:
        if maximum_inclusive and number > maximum:
            _fail(f"{name} must be <= {maximum}")
        if not maximum_inclusive and number >= maximum:
            _fail(f"{name} must be < {maximum}")
    return number


def _class_weight(value: Any, name: str) -> None:
    if value is None:
        return
    if value == "balanced":
        return
    _number(value, name, minimum=0.0, minimum_inclusive=False)


def _validate_data(raw: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(_DATA_DEFAULTS)
    data.update(raw)
    _unknown_keys(data, _DATA_KEYS, "data")

    mode = _string(data["mode"], "data.mode")
    if mode not in DATA_MODES:
        _fail(f"data.mode must be one of {', '.join(DATA_MODES)}")
    data["mode"] = mode

    data["root"] = _string(data["root"], "data.root", allow_none=True)
    data["n_bins"] = _integer(data["n_bins"], "data.n_bins", minimum=50)
    if data["n_bins"] > 2000:
        _fail("data.n_bins must be <= 2000")

    split_version = _string(data["split_version"], "data.split_version")
    if any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for char in split_version
    ):
        _fail("data.split_version may only contain letters, digits, '.', '_' or '-'")
    data["split_version"] = split_version

    fingerprint = data["expected_dataset_fingerprint"]
    if fingerprint is not None:
        fingerprint = _string(fingerprint, "data.expected_dataset_fingerprint")
        if len(fingerprint) != 40 or any(
            c not in "0123456789abcdef" for c in fingerprint
        ):
            _fail("data.expected_dataset_fingerprint must be a 40-char lowercase sha1")
    data["expected_dataset_fingerprint"] = fingerprint

    data["stub_targets"] = _integer(
        data["stub_targets"], "data.stub_targets", minimum=10
    )
    data["stub_seed"] = _integer(data["stub_seed"], "data.stub_seed", minimum=0)
    data["verify_content"] = _boolean(data["verify_content"], "data.verify_content")
    return data


def _validate_features(raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {"set"}
    _unknown_keys(raw, allowed, "features")
    feature_set = raw.get("set", "catalog_v1")
    feature_set = _string(feature_set, "features.set")
    if feature_set not in feature_sets.FEATURE_SETS:
        _fail(
            "features.set must be one of "
            + ", ".join(sorted(feature_sets.FEATURE_SETS))
        )
    return {"set": feature_set}


def _validate_model_params(model: str, raw: dict[str, Any]) -> dict[str, Any]:
    defaults = _BASELINE_DEFAULTS if model == "baseline" else _CNN_DEFAULTS
    params = copy.deepcopy(defaults)
    params.update(raw)
    _unknown_keys(params, _MODEL_KEYS[model], "model_params")

    if model == "baseline":
        params["n_estimators"] = _integer(
            params["n_estimators"], "model_params.n_estimators", minimum=1
        )
        if params["n_estimators"] > 5000:
            _fail("model_params.n_estimators must be <= 5000")
        params["max_depth"] = _integer(
            params["max_depth"], "model_params.max_depth", minimum=1
        )
        if params["max_depth"] > 30:
            _fail("model_params.max_depth must be <= 30")
        params["learning_rate"] = _number(
            params["learning_rate"],
            "model_params.learning_rate",
            minimum=0.0,
            maximum=1.0,
            minimum_inclusive=False,
        )
        params["subsample"] = _number(
            params["subsample"],
            "model_params.subsample",
            minimum=0.0,
            maximum=1.0,
            minimum_inclusive=False,
        )
        params["min_samples_leaf"] = _integer(
            params["min_samples_leaf"], "model_params.min_samples_leaf", minimum=1
        )
        max_features = params["max_features"]
        if max_features not in (None, "sqrt", "log2"):
            if not isinstance(max_features, int | float) or isinstance(
                max_features, bool
            ):
                _fail(
                    "model_params.max_features must be null, 'sqrt', 'log2' or a float"
                )
            _number(
                max_features,
                "model_params.max_features",
                minimum=0.0,
                maximum=1.0,
                minimum_inclusive=False,
                maximum_inclusive=False,
            )
        _class_weight(params["class_weight"], "model_params.class_weight")
        return params

    channels = params["channels"]
    if not isinstance(channels, list) or len(channels) != 3:
        _fail("model_params.channels must be a list of exactly 3 integers")
    params["channels"] = [
        _integer(channel, f"model_params.channels[{index}]", minimum=1)
        for index, channel in enumerate(channels)
    ]
    if any(channel > 512 for channel in params["channels"]):
        _fail("model_params.channels values must be <= 512")

    params["kernel_size"] = _integer(
        params["kernel_size"], "model_params.kernel_size", minimum=3
    )
    if params["kernel_size"] % 2 == 0:
        _fail("model_params.kernel_size must be odd")
    if params["kernel_size"] > 31:
        _fail("model_params.kernel_size must be <= 31")
    params["dropout"] = _number(
        params["dropout"],
        "model_params.dropout",
        minimum=0.0,
        maximum=1.0,
        maximum_inclusive=False,
    )
    params["fc_dim"] = _integer(params["fc_dim"], "model_params.fc_dim", minimum=1)
    if params["fc_dim"] > 2048:
        _fail("model_params.fc_dim must be <= 2048")
    _class_weight(params["class_weight"], "model_params.class_weight")
    return params


def _validate_training(model: str, raw: dict[str, Any]) -> dict[str, Any]:
    training = copy.deepcopy(_TRAINING_DEFAULTS[model])
    training.update(raw)
    _unknown_keys(training, _TRAINING_KEYS[model], "training")

    selection = _string(training["threshold_selection"], "training.threshold_selection")
    if selection not in THRESHOLD_SELECTIONS:
        _fail(
            "training.threshold_selection must be one of "
            + ", ".join(THRESHOLD_SELECTIONS)
        )
    training["threshold_selection"] = selection
    training["threshold"] = _number(
        training["threshold"],
        "training.threshold",
        minimum=0.0,
        maximum=1.0,
        minimum_inclusive=False,
        maximum_inclusive=False,
    )
    training["max_train_seconds"] = _number(
        training["max_train_seconds"],
        "training.max_train_seconds",
        minimum=0.0,
        minimum_inclusive=False,
    )

    if model == "cnn":
        training["max_epochs"] = _integer(
            training["max_epochs"], "training.max_epochs", minimum=1
        )
        training["batch_size"] = _integer(
            training["batch_size"], "training.batch_size", minimum=2
        )
        if training["batch_size"] > 4096:
            _fail("training.batch_size must be <= 4096")
        training["learning_rate"] = _number(
            training["learning_rate"],
            "training.learning_rate",
            minimum=0.0,
            minimum_inclusive=False,
        )
        training["weight_decay"] = _number(
            training["weight_decay"], "training.weight_decay", minimum=0.0
        )
        training["patience"] = _integer(
            training["patience"], "training.patience", minimum=0
        )
        training["num_threads"] = _integer(
            training["num_threads"], "training.num_threads", minimum=1
        )
        if training["num_threads"] > 64:
            _fail("training.num_threads must be <= 64")
        augmentation = _mapping(training["augmentation"], "training.augmentation")
        _unknown_keys(
            augmentation, {"phase_shift", "noise_ppm"}, "training.augmentation"
        )
        augmentation.setdefault("phase_shift", False)
        augmentation.setdefault("noise_ppm", 0.0)
        augmentation["phase_shift"] = _boolean(
            augmentation["phase_shift"], "training.augmentation.phase_shift"
        )
        augmentation["noise_ppm"] = _number(
            augmentation["noise_ppm"],
            "training.augmentation.noise_ppm",
            minimum=0.0,
        )
        training["augmentation"] = augmentation
    return training


@dataclass(frozen=True)
class RunConfig:
    """Validated, fully-defaulted run configuration."""

    raw: dict[str, Any]

    # -- construction ---------------------------------------------------
    @classmethod
    def from_dict(cls, raw: Any, *, source: str = "<dict>") -> RunConfig:
        if not isinstance(raw, dict):
            _fail(f"{source}: config must be a JSON object")
        raw = copy.deepcopy(raw)
        _unknown_keys(raw, _TOP_LEVEL_KEYS, f"{source}: config")

        name = _string(raw.get("name"), f"{source}: name")
        model = _string(raw.get("model"), f"{source}: model")
        if model not in MODELS:
            _fail(f"{source}: model must be one of {', '.join(MODELS)}")
        seed = _integer(raw.get("seed", 42), f"{source}: seed", minimum=0)
        if seed > 2**32 - 1:
            _fail(f"{source}: seed must fit in uint32")

        hypothesis_id = raw.get("hypothesis_id")
        if hypothesis_id is not None:
            hypothesis_id = _string(hypothesis_id, f"{source}: hypothesis_id")
        notes = raw.get("notes")
        if notes is not None:
            notes = _string(notes, f"{source}: notes")

        merged = {
            "name": name,
            "model": model,
            "seed": seed,
            "hypothesis_id": hypothesis_id,
            "data": _validate_data(_mapping(raw.get("data", {}), "data")),
            "features": _validate_features(
                _mapping(raw.get("features", {}), "features")
            ),
            "model_params": _validate_model_params(
                model, _mapping(raw.get("model_params", {}), "model_params")
            ),
            "training": _validate_training(
                model, _mapping(raw.get("training", {}), "training")
            ),
            "notes": notes,
        }
        return cls(raw=merged)

    @classmethod
    def from_path(cls, path: str | Path) -> RunConfig:
        config_path = Path(path).expanduser()
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config not found: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(
                f"config is not valid JSON: {config_path}: {exc}"
            ) from exc
        return cls.from_dict(raw, source=str(config_path))

    # -- identity -------------------------------------------------------
    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.raw)

    def config_hash(self) -> str:
        canonical = json.dumps(
            self.raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()

    # -- convenient accessors ------------------------------------------
    @property
    def name(self) -> str:
        return self.raw["name"]

    @property
    def model(self) -> str:
        return self.raw["model"]

    @property
    def seed(self) -> int:
        return self.raw["seed"]

    @property
    def hypothesis_id(self) -> str | None:
        return self.raw["hypothesis_id"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def features(self) -> dict[str, Any]:
        return self.raw["features"]

    @property
    def model_params(self) -> dict[str, Any]:
        return self.raw["model_params"]

    @property
    def training(self) -> dict[str, Any]:
        return self.raw["training"]

    @property
    def mode(self) -> str:
        return self.data["mode"]

    @property
    def n_bins(self) -> int:
        return self.data["n_bins"]

    @property
    def split_version(self) -> str:
        return self.data["split_version"]

    @property
    def feature_set(self) -> str:
        return self.features["set"]

    @property
    def data_dir(self) -> Path:
        root = self.data["root"]
        if root:
            return paths.resolve(root)
        return paths.mode_root(self.mode)

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def splits_dir(self) -> Path:
        return self.data_dir / "splits"

    @property
    def labels_path(self) -> Path:
        return self.data_dir / "koi.csv"

    @property
    def expected_dataset_fingerprint(self) -> str | None:
        return self.data["expected_dataset_fingerprint"]

    @property
    def verify_content(self) -> bool:
        return self.data["verify_content"]

    @property
    def stub_targets(self) -> int:
        return self.data["stub_targets"]

    @property
    def stub_seed(self) -> int:
        return self.data["stub_seed"]


def load_config(path: str | Path) -> RunConfig:
    """Load a config and apply the one documented environment override.

    ``DATA_MODE`` overrides ``data.mode``. The override is folded into the
    effective config *before* hashing, so a run can never claim a hash that
    hides a different data mode.
    """
    config_path = Path(path).expanduser()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config is not valid JSON: {config_path}: {exc}") from exc

    override = os.environ.get("DATA_MODE")
    if override:
        mode = override.strip().lower()
        if mode not in DATA_MODES:
            raise ConfigError(f"DATA_MODE must be one of {', '.join(DATA_MODES)}")
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path}: config must be a JSON object")
        data = raw.setdefault("data", {})
        if not isinstance(data, dict):
            raise ConfigError(f"{config_path}: data must be a JSON object")
        data["mode"] = mode

    return RunConfig.from_dict(raw, source=str(config_path))
