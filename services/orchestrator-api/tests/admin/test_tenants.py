import pytest


@pytest.mark.asyncio
class TestSuperAdminGuard:
    async def test_admin_cannot_access_tenants(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_tenants(self, async_client):
        resp = await async_client.get("/admin/tenants")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestTenantCRUD:
    async def test_list_tenants_returns_orgs(self, async_client, admin_seed, super_admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        org_names = [t["name"] for t in body]
        assert admin_seed["tenant_org"].name in org_names

    async def test_create_tenant(self, async_client, super_admin_token):
        resp = await async_client.post(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": "New Corp", "plan_tier": "pro", "workspace_limit": 10},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Corp"
        assert body["plan_tier"] == "pro"
        assert body["workspace_limit"] == 10
        assert body["is_active"] is True

    async def test_get_tenant(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.get(
            f"/admin/tenants/{org_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == org_id

    async def test_get_tenant_not_found(self, async_client, super_admin_token):
        import uuid
        resp = await async_client.get(
            f"/admin/tenants/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 404

    async def test_update_tenant_plan_tier(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.patch(
            f"/admin/tenants/{org_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"plan_tier": "enterprise"},
        )
        assert resp.status_code == 200
        assert resp.json()["plan_tier"] == "enterprise"

    async def test_suspend_tenant(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.delete(
            f"/admin/tenants/{org_id}/suspend",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is False
        assert body["suspended_at"] is not None
