"""Simple test to verify models work."""

import tempfile
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


# Test basic SQLModel with relationships
class TestEnum(str, Enum):
    A = "a"
    B = "b"


class Parent(SQLModel, table=True):
    __tablename__ = "parent"
    id: str = Field(primary_key=True)
    name: str
    status: TestEnum = Field(default=TestEnum.A)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    children: list["Child"] = Relationship(back_populates="parent")


class Child(SQLModel, table=True):
    __tablename__ = "child"
    id: str = Field(primary_key=True)
    parent_id: str = Field(foreign_key="parent.id")
    name: str
    parent: "Parent" = Relationship(back_populates="children")


with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    db_path = Path(f.name)

engine = create_engine(f"sqlite:///{db_path}", echo=True)
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    try:
        parent = Parent(id="p1", name="Parent")
        child = Child(id="c1", parent_id="p1", name="Child")
        session.add(parent)
        session.add(child)
        session.commit()
        print("Success!")
        print(f"parent status: {parent.status}")
        print(f"parent created_at: {parent.created_at}")
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error: {e}")
