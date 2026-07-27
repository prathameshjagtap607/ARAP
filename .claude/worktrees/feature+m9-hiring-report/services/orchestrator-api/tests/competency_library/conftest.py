import os
import pytest
import pytest_asyncio
import fakeredis
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
import src.models  # noqa: F401
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    _Session = sessionmaker(engine)
    s = _Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def seed(db):
    org = Org(name="CompLib Org")
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email="user@complib.com", role="user",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(user)
    db.commit()
    db.refresh(org)
    db.refresh(user)
    return {"org": org, "user": user}


@pytest.fixture
def user_token(seed):
    org = seed["org"]
    user = seed["user"]
    return create_access_token({
        "sub": str(user.id),
        "role": "user",
        "org_id": str(org.id),
    })


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.main import app
    from src.database import get_db, get_redis
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
