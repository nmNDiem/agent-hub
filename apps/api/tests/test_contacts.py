import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_leads import (
    AppFactory,
    create_published_agent,
    create_visitor,
    csrf_headers,
    lead_payload,
    visitor_headers,
)

from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.models import WorkspaceMember

pytest_plugins = ("test_leads",)


def test_contact_timeline_duplicate_merge_reversal_and_tenant_scope(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        shop_a = create_published_agent(owner_a, "contact-a@example.com", "contact-a")
        shop_b = create_published_agent(owner_b, "contact-b@example.com", "contact-b")

        for index, name in enumerate(("=Khách một", "Khách hai"), start=1):
            token, conversation, _ = create_visitor(owner_a, shop_a["public_agent_id"])
            created = owner_a.post(
                f"/api/v1/widget/conversations/{conversation}/leads",
                json=lead_payload(name=name, email="shared@example.com"),
                headers=visitor_headers(token, f"contact-create-{index}"),
            )
            assert created.status_code == 201, created.text

        base = f"/api/v1/workspaces/{shop_a['workspace_id']}/contacts"
        listed = owner_a.get(base)
        assert listed.status_code == 200, listed.text
        assert listed.headers["cache-control"] == "no-store"
        contacts = listed.json()["items"]
        assert len(contacts) == 2

        target, source = contacts
        detail = owner_a.get(f"{base}/{target['public_id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["duplicate_candidates"] == [
            {
                "public_id": source["public_id"],
                "display_name": source["display_name"],
                "matching_identity_types": ["email"],
            }
        ]
        assert owner_b.get(f"{base}/{target['public_id']}").status_code == 404
        assert (
            owner_b.get(
                f"/api/v1/workspaces/{shop_b['workspace_id']}/contacts/{target['public_id']}"
            ).status_code
            == 404
        )
        other_csrf = csrf_headers(owner_b)
        assert owner_b.get(base).status_code == 404
        assert owner_b.get(f"{base}/export.csv").status_code == 404
        assert (
            owner_b.patch(
                f"{base}/{target['public_id']}",
                json={"state_version": target["state_version"], "update_display_name": True},
                headers=other_csrf,
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"{base}/{target['public_id']}/notes",
                json={"body": "Sai workspace"},
                headers=other_csrf,
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"{base}/{target['public_id']}/tags",
                json={"name": "Sai workspace"},
                headers=other_csrf,
            ).status_code
            == 404
        )
        assert (
            owner_b.post(
                f"{base}/{target['public_id']}/merges",
                json={
                    "source_public_id": source["public_id"],
                    "source_state_version": source["state_version"],
                    "target_state_version": target["state_version"],
                    "reason": "Sai workspace",
                },
                headers=other_csrf,
            ).status_code
            == 404
        )

        assert (
            owner_a.post(
                f"{base}/{target['public_id']}/notes", json={"body": "Không có CSRF"}
            ).status_code
            == 403
        )
        note = owner_a.post(
            f"{base}/{target['public_id']}/notes",
            json={"body": "Ưu tiên liên hệ buổi sáng"},
            headers=csrf_headers(owner_a),
        )
        assert note.status_code == 204, note.text
        tagged = owner_a.post(
            f"{base}/{target['public_id']}/tags",
            json={"name": "VIP"},
            headers=csrf_headers(owner_a),
        )
        assert tagged.status_code == 204, tagged.text
        detail_after_tag = owner_a.get(f"{base}/{target['public_id']}").json()
        assert [tag["name"] for tag in detail_after_tag["contact"]["tags"]] == ["VIP"]

        merged = owner_a.post(
            f"{base}/{target['public_id']}/merges",
            json={
                "source_public_id": source["public_id"],
                "source_state_version": source["state_version"],
                "target_state_version": target["state_version"],
                "reason": "Khách xác nhận cùng hồ sơ",
            },
            headers=csrf_headers(owner_a),
        )
        assert merged.status_code == 201, merged.text
        merge_id = merged.json()["merge_id"]
        assert (
            owner_b.post(
                f"{base}/{target['public_id']}/merges/{merge_id}/reverse",
                headers=other_csrf,
            ).status_code
            == 404
        )
        assert len(owner_a.get(base).json()["items"]) == 1

        merged_detail = owner_a.get(f"{base}/{target['public_id']}")
        assert merged_detail.status_code == 200
        assert merged_detail.json()["active_merges"][0]["id"] == merge_id
        assert any(item["kind"] == "merge" for item in merged_detail.json()["timeline"])
        reversed_merge = owner_a.post(
            f"{base}/{target['public_id']}/merges/{merge_id}/reverse",
            headers=csrf_headers(owner_a),
        )
        assert reversed_merge.status_code == 204, reversed_merge.text
        assert len(owner_a.get(base).json()["items"]) == 2

        exported = owner_a.get(f"{base}/export.csv")
        assert exported.status_code == 200
        assert "'=Khách một" in exported.content.decode("utf-8-sig")

        async def add_member() -> int:
            async with session_factory() as session, session.begin():
                user = await session.scalar(
                    select(User).where(User.normalized_email == "contact-b@example.com")
                )
                assert user is not None
                membership = WorkspaceMember(
                    workspace_id=UUID(shop_a["workspace_id"]),
                    user_id=user.id,
                    role="member",
                )
                session.add(membership)
                await session.flush()
                return membership.id

        member_id = asyncio.run(add_member())
        member_list = owner_b.get(base)
        assert member_list.status_code == 200
        member_contact = member_list.json()["items"][0]
        claim = owner_b.patch(
            f"{base}/{member_contact['public_id']}",
            json={
                "state_version": member_contact["state_version"],
                "assigned_member_id": member_id,
            },
            headers=csrf_headers(owner_b),
        )
        assert claim.status_code == 204, claim.text
        assert owner_b.get(f"{base}/export.csv").status_code == 403
