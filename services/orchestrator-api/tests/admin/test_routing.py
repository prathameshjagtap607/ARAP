import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def seed_routing_configs(db):
    """Seed the 3 standard routing configs that migration 0007 would add in production."""
    db.execute(
        text("""
            INSERT INTO model_routing_configs
                (agent_name, provider, model_id, fallback_provider, fallback_model_id, is_active)
            VALUES
                ('question_generator', 'anthropic', 'claude-sonnet-4-5-20251001', NULL, NULL, true),
                ('report_writer',      'anthropic', 'claude-sonnet-4-5-20251001', NULL, NULL, true),
                ('scorer',             'anthropic', 'claude-haiku-4-5-20251001',  NULL, NULL, true)
            ON CONFLICT (agent_name) DO NOTHING
        """)
    )
    db.commit()


@pytest.mark.asyncio
class TestModelRouting:
    async def test_list_routing_configs(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/routing",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        agent_names = [r["agent_name"] for r in body]
        assert "question_generator" in agent_names
        assert "report_writer" in agent_names
        assert "scorer" in agent_names

    async def test_update_routing_config(self, async_client, super_admin_token):
        resp = await async_client.patch(
            "/admin/routing/question_generator",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "claude-haiku-4-5-20251001"},
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "claude-haiku-4-5-20251001"
        assert resp.json()["agent_name"] == "question_generator"

    async def test_update_invalidates_redis_cache(self, async_client, super_admin_token, r):
        # Seed a value in Redis as if it were cached
        r.setex("routing:report_writer", 30, '{"agent_name":"report_writer","provider":"anthropic","model_id":"old-model","fallback_provider":null,"fallback_model_id":null}')
        assert r.get("routing:report_writer") is not None

        await async_client.patch(
            "/admin/routing/report_writer",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "claude-sonnet-5"},
        )
        # Cache should be cleared after update
        assert r.get("routing:report_writer") is None

    async def test_update_unknown_agent_returns_404(self, async_client, super_admin_token):
        resp = await async_client.patch(
            "/admin/routing/nonexistent_agent",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "some-model"},
        )
        assert resp.status_code == 404

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/routing",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
