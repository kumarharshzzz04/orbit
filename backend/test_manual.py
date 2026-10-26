"""Manual test script to verify models work."""

import tempfile
import traceback
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine


# Test basic SQLModel first
class TestEnum(str, Enum):
    A = "a"
    B = "b"


class TestModel(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    status: TestEnum = Field(default=TestEnum.A)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


print("Testing basic model...")
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    db_path = Path(f.name)

engine = create_engine(f"sqlite:///{db_path}", echo=True)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    try:
        obj = TestModel(id="test1", name="Test")
        session.add(obj)
        session.commit()
        print("Basic model Success!")
        print(f"status: {obj.status}")
        print(f"created_at: {obj.created_at}")
    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}")
