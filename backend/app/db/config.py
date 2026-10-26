"""Database configuration and connection handling for ORBIT backend."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Database file location
DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "orbit.db"


def get_database_url(db_path: Path | None = None) -> str:
    """Get SQLite database URL."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def create_engine_with_pragmas(db_path: Path | None = None) -> Engine:
    """Create SQLite engine with required pragmas enabled."""
    engine = create_engine(
        get_database_url(db_path),
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        # Use WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Synchronous=NORMAL for better performance with WAL
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


# Global engine instance (initialized on first use)
_engine: Engine | None = None


def get_engine(db_path: Path | None = None) -> Engine:
    """Get or create the global engine instance."""
    global _engine
    # Check environment variable for test database path
    import os

    if _engine is None:
        effective_path = db_path
        if effective_path is None:
            env_path = os.environ.get("ORBIT_DB_PATH")
            if env_path:
                effective_path = Path(env_path)
        _engine = create_engine_with_pragmas(effective_path)
    return _engine


def init_db(db_path: Path | None = None) -> None:
    """Initialize database: create all tables."""
    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)


def get_session(db_path: Path | None = None) -> Generator[Session, None, None]:
    """Get a database session (for FastAPI dependency injection)."""
    engine = get_engine(db_path)
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope(db_path: Path | None = None) -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    engine = get_engine(db_path)
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database(db_path: Path | None = None) -> None:
    """Drop and recreate all tables (for testing)."""
    engine = get_engine(db_path)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
