import os

import pytest
import src.models  # noqa: F401 — registers all models
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.models.base import Base

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/arap_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, echo=False)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine):
    Session = sessionmaker(engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
