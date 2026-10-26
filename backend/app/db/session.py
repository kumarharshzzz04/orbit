"""Database session management and transaction helpers."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TypeVar

from sqlalchemy import exc as sa_exc
from sqlmodel import Session, select, text

from .models import ExecutionStatus, Experiment, Verdict

T = TypeVar("T")

# Transaction retry configuration
MAX_RETRIES = 5
BASE_RETRY_DELAY = 0.05  # 50ms


def _is_locked_error(error: Exception) -> bool:
    """Check if error indicates database is locked."""
    error_str = str(error).lower()
    return (
        "database is locked" in error_str
        or "sqlite_busy" in error_str
        or isinstance(error, sa_exc.OperationalError)
        and "locked" in error_str
    )


@contextmanager
def immediate_transaction(session: Session) -> Generator[Session, None, None]:
    """
    Context manager for BEGIN IMMEDIATE transaction.

    Acquires write lock immediately, preventing other writers.
    Retries on SQLITE_BUSY with exponential backoff.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Acquire write lock immediately
            session.exec(text("BEGIN IMMEDIATE TRANSACTION"))
            yield session
            session.commit()
            return
        except Exception as e:
            session.rollback()
            if _is_locked_error(e) and attempt < MAX_RETRIES - 1:
                time.sleep(BASE_RETRY_DELAY * (attempt + 1))
                continue
            raise
    raise RuntimeError("Failed to acquire database lock after retries")


def run_in_transaction(
    session_factory: Callable[[], Session],
    operation: Callable[[Session], T],
    max_retries: int = MAX_RETRIES,
) -> T:
    """
    Run an operation in a new BEGIN IMMEDIATE transaction with retries.

    Creates a fresh session for each attempt to avoid transaction state issues.
    """
    last_error = None
    for attempt in range(max_retries):
        session = session_factory()
        try:
            session.exec(text("BEGIN IMMEDIATE TRANSACTION"))
            result = operation(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            last_error = e
            if _is_locked_error(e) and attempt < max_retries - 1:
                time.sleep(BASE_RETRY_DELAY * (attempt + 1))
                continue
            raise
        finally:
            session.close()
    raise RuntimeError(
        f"Transaction failed after {max_retries} retries"
    ) from last_error


def get_current_champion(session: Session) -> Experiment | None:
    """
    Get the current champion experiment.

    Champion = highest-F1 KEEP verdict with COMPLETED execution status.
    """
    return session.exec(
        select(Experiment)
        .where(Experiment.verdict == Verdict.KEEP)
        .where(Experiment.execution_status == ExecutionStatus.COMPLETED)
        .order_by(text("json_extract(metrics, '$.f1') DESC"))
        .limit(1)
    ).first()
