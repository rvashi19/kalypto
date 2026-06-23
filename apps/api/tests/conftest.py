import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

TEST_DATABASE_PATH = Path(__file__).resolve().with_name("test_phase0.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

from app.db.base import Base
from app.db.session import SessionLocal, engine


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    test_session = SessionLocal()
    try:
        yield test_session
    finally:
        test_session.close()
