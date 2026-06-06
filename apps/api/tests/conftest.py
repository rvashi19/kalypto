import os
from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///./apps/api/tests/test_phase0.db"

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
