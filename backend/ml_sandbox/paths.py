"""Filesystem layout for the ML sandbox.

Everything the sandbox writes lives under ``data/`` (git-ignored) except run
outputs, which the caller chooses with ``--out`` (normally ``artifacts/<run_id>/``).
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def data_root() -> Path:
    """Base data directory, overridable with ``ORBIT_DATA_DIR``."""
    override = os.environ.get("ORBIT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "data"


def mode_root(mode: str) -> Path:
    """Default data directory for a data mode (``stub`` or ``live``)."""
    return data_root() / mode


def resolve(path: str | Path) -> Path:
    """Resolve a user-supplied path against the repository root."""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def artifacts_root() -> Path:
    return REPO_ROOT / "artifacts"


def relpath(path: Path) -> str:
    """Display a path relative to the repo when possible, POSIX style."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
