import pytest


@pytest.mark.asyncio
class TestSuperAdminGuard:
    async def test_admin_cannot_access_tenants(self, async_client, admin_seed, admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_tenants(self, async_client):
        resp = await async_client.get("/admin/tenants")
        assert resp.status_code == 401
