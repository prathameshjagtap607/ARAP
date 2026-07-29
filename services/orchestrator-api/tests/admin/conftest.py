import os
import uuid as _uuid

import fakeredis
import pytest
import pytest_asyncio
import src.models  # noqa: F401
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://arap:arap@localhost:5434/arap_test"
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
def admin_seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    system_org = Org(name=f"System Org {uid}")
    tenant_org = Org(name=f"Tenant Org {uid}")
    db.add_all([system_org, tenant_org])
    db.flush()

    super_admin = User(
        org_id=system_org.id,
        email=f"superadmin-{uid}@system.com",
        role="super_admin",
        password_hash=pwd_context.hash("x"),
    )
    regular_admin = User(
        org_id=tenant_org.id,
        email=f"admin-{uid}@tenant.com",
        role="admin",
        password_hash=pwd_context.hash("x"),
    )
    db.add_all([super_admin, regular_admin])
    db.flush()
    db.commit()
    return {
        "system_org": system_org,
        "tenant_org": tenant_org,
        "super_admin": super_admin,
        "regular_admin": regular_admin,
    }


@pytest.fixture
def super_admin_token(admin_seed: dict) -> str:
    return create_access_token({
        "sub": str(admin_seed["super_admin"].id),
        "role": "super_admin",
        "org_id": str(admin_seed["system_org"].id),
    })


@pytest.fixture
def admin_token(admin_seed: dict) -> str:
    return create_access_token({
        "sub": str(admin_seed["regular_admin"].id),
        "role": "admin",
        "org_id": str(admin_seed["tenant_org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session, r):
    from src.database import get_db, get_redis
    from src.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
