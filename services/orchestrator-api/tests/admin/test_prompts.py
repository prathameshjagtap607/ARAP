import pytest


@pytest.mark.asyncio
class TestPromptLibrary:
    async def _create_template(self, async_client, super_admin_token, agent_name="question_generator", version="v1.0"):
        resp = await async_client.post(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "agent_name": agent_name,
                "version": version,
                "template_body": f"You are a {agent_name} assistant. Generate a question about {{topic}}.",
            },
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_create_prompt_template(self, async_client, super_admin_token):
        body = await self._create_template(async_client, super_admin_token)
        assert body["agent_name"] == "question_generator"
        assert body["version"] == "v1.0"
        assert body["is_active"] is False

    async def test_list_all_prompts(self, async_client, super_admin_token):
        await self._create_template(async_client, super_admin_token, version="v-list-test")
        resp = await async_client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_versions_for_agent(self, async_client, super_admin_token):
        await self._create_template(async_client, super_admin_token, version="v-agent-list")
        resp = await async_client.get(
            "/admin/prompts/question_generator",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert all(t["agent_name"] == "question_generator" for t in resp.json())

    async def test_activate_prompt(self, async_client, super_admin_token):
        t = await self._create_template(async_client, super_admin_token, version="v-activate")
        resp = await async_client.post(
            f"/admin/prompts/{t['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_activate_deactivates_prior(self, async_client, super_admin_token):
        import uuid
        agent = f"scorer-{uuid.uuid4().hex[:6]}"
        t1 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v1")
        t2 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v2")

        await async_client.post(
            f"/admin/prompts/{t1['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        resp = await async_client.post(
            f"/admin/prompts/{t2['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

        # t1 must now be inactive
        resp2 = await async_client.get(
            f"/admin/prompts/{agent}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        versions = {t["id"]: t for t in resp2.json()}
        assert versions[t1["id"]]["is_active"] is False

    async def test_rollback_prompt(self, async_client, super_admin_token):
        import uuid
        agent = f"report_writer-{uuid.uuid4().hex[:6]}"
        t1 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v1")
        t2 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v2")

        await async_client.post(
            f"/admin/prompts/{t1['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        await async_client.post(
            f"/admin/prompts/{t2['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

        resp = await async_client.post(
            f"/admin/prompts/{t2['id']}/rollback",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == t1["id"]
        assert resp.json()["is_active"] is True

    async def test_audit_returns_sessions(self, async_client, super_admin_token):
        t = await self._create_template(async_client, super_admin_token, version="v-audit")
        resp = await async_client.get(
            f"/admin/prompts/{t['id']}/audit",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
