import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
import src.models  # noqa: F401
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def async_client(db):
    from src.database import get_db
    from src.main import app
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestScoreTrendsRoute:
    async def test_returns_200_with_data(self, async_client, analytics_seed, user_token):
        with patch("src.modules.analytics.router.get_redis") as mock_redis:
            mock_redis.return_value = MagicMock(get=lambda k: None, setex=lambda *a: None, scan=lambda *a, **kw: (0, []))
            resp = await async_client.get(
                "/analytics/score-trends",
                headers={"Authorization": f"Bearer {user_token}"},
                params={
                    "from_date": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
                    "to_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_requires_auth(self, async_client):
        resp = await async_client.get("/analytics/score-trends")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestFunnelRoute:
    async def test_returns_200(self, async_client, analytics_seed, user_token):
        with patch("src.modules.analytics.router.get_redis") as mock_redis:
            mock_redis.return_value = MagicMock(get=lambda k: None, setex=lambda *a: None, scan=lambda *a, **kw: (0, []))
            resp = await async_client.get(
                "/analytics/funnel",
                headers={"Authorization": f"Bearer {user_token}"},
                params={
                    "from_date": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
                    "to_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "rows" in body
        assert "totals" in body


@pytest.mark.asyncio
class TestBenchmarkRoute:
    async def test_returns_404_for_unknown_session(self, async_client, analytics_seed, user_token):
        with patch("src.modules.analytics.router.get_redis") as mock_redis:
            mock_redis.return_value = MagicMock(get=lambda k: None, setex=lambda *a: None, scan=lambda *a, **kw: (0, []))
            resp = await async_client.get(
                f"/analytics/benchmarks/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {user_token}"},
            )
        assert resp.status_code == 404

    async def test_returns_200_for_seeded_session(self, async_client, analytics_seed, user_token):
        session_id = analytics_seed["sessions"][0].id
        with patch("src.modules.analytics.router.get_redis") as mock_redis:
            mock_redis.return_value = MagicMock(get=lambda k: None, setex=lambda *a: None, scan=lambda *a, **kw: (0, []))
            resp = await async_client.get(
                f"/analytics/benchmarks/{session_id}",
                headers={"Authorization": f"Bearer {user_token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "percentile" in body
        assert "peer_count" in body
