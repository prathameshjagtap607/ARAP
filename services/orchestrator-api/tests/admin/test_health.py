import pytest


@pytest.mark.asyncio
class TestSystemHealth:
    async def test_overview_returns_expected_shape(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/overview",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "queue_depth" in body
        assert "error_rate_24h" in body
        assert "p50_seconds" in body
        assert "p95_seconds" in body
        assert "p99_seconds" in body
        assert "total_sessions_24h" in body

    async def test_incidents_returns_list(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/incidents",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_fraud_flags_returns_expected_shape(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/fraud-flags",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_flags" in body
        assert "false_positive_count" in body
        assert "false_positive_rate" in body

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/health/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
