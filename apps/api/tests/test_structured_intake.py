import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_leads import (
    AppFactory,
    create_published_agent,
    create_visitor,
    csrf_headers,
    visitor_headers,
)

from agent_hub_api.agents.models import Agent
from agent_hub_api.agents.runtime import GroundedAgentRuntime
from agent_hub_api.contacts.follow_up import (
    FollowUpActionContext,
    FollowUpActionInput,
    FollowUpActionService,
)
from agent_hub_api.contacts.intake import (
    IntakeActionContext,
    IntakeActionInput,
    IntakeActionService,
)
from agent_hub_api.contacts.models import IntakeActionExecution, IntakeSubmission
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.leads.models import Lead
from agent_hub_api.operations.retention import RetentionSweeper

pytest_plugins = ("test_leads",)


def intake_definition() -> dict[str, object]:
    return {
        "purpose": "Tư vấn giải pháp phù hợp",
        "disclosure": "Mình xin phép ghi nhận để đội ngũ tư vấn hỗ trợ bạn tốt hơn nhé.",
        "fields": [
            {
                "semantic": "name",
                "label": "Tên khách",
                "kind": "short_text",
                "required": True,
                "options": [],
            },
            {
                "semantic": "email",
                "label": "Email liên hệ",
                "kind": "email",
                "required": True,
                "options": [],
            },
            {
                "semantic": "context",
                "label": "Nhu cầu",
                "kind": "long_text",
                "required": True,
                "options": [],
            },
        ],
    }


def test_intake_schema_excludes_raw_answers_from_execution_evidence() -> None:
    execution_columns = set(IntakeActionExecution.__table__.columns.keys())
    assert execution_columns.isdisjoint(
        {"answers_json", "definition_json", "message_text", "prompt", "tool_arguments"}
    )
    assert {"answers_json", "definition_json"}.issubset(
        set(IntakeSubmission.__table__.columns.keys())
    )


def test_intake_tool_is_available_only_when_bound() -> None:
    without_intake = GroundedAgentRuntime._tool_definitions(
        catalog_available=False, intake_available=False
    )
    with_intake = GroundedAgentRuntime._tool_definitions(
        catalog_available=False, intake_available=True
    )
    assert "submit_structured_intake" not in {tool.name for tool in without_intake}
    assert "submit_structured_intake" in {tool.name for tool in with_intake}


def test_structured_intake_commits_atomically_and_requires_human_qualification(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    settings = Settings(
        app_env="test",
        jwt_signing_key="test-signing-key-with-at-least-32-bytes",
    )
    with TestClient(app) as owner:
        published = create_published_agent(owner, "intake@example.com", "intake")
        prohibited_definition = intake_definition()
        prohibited_fields = prohibited_definition["fields"]
        assert isinstance(prohibited_fields, list)
        assert isinstance(prohibited_fields[0], dict)
        prohibited_fields[0]["label"] = "Tọa độ GPS chính xác"
        prohibited = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/agents/{published['public_agent_id']}",
            json={"intake_definition": prohibited_definition},
            headers=csrf_headers(owner),
        )
        assert prohibited.status_code == 422

        configured = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/agents/{published['public_agent_id']}",
            json={
                "follow_up_action_enabled": True,
                "intake_action_enabled": True,
                "intake_definition": intake_definition(),
            },
            headers=csrf_headers(owner),
        )
        assert configured.status_code == 200, configured.text
        materialized = configured.json()["intake_definition"]
        assert materialized["disclosure_version"].startswith("intake-v1-")
        assert all(field["key"] for field in materialized["fields"])

        republished = owner.post(f"{published['base']}/publish", headers=csrf_headers(owner))
        assert republished.status_code == 200, republished.text

        token, conversation_public_id, _ = create_visitor(owner, published["public_agent_id"])
        turn = owner.post(
            f"/api/v1/widget/conversations/{conversation_public_id}/messages",
            json={"message": "Mình là An, email an@example.com và cần tư vấn gói phù hợp."},
            headers=visitor_headers(token, "intake-turn-0001"),
        )
        assert turn.status_code == 200, turn.text

        async def context() -> IntakeActionContext:
            async with session_factory() as session:
                agent = await session.scalar(
                    select(Agent).where(Agent.public_id == UUID(published["public_agent_id"]))
                )
                conversation = await session.scalar(
                    select(Conversation).where(
                        Conversation.public_id == UUID(conversation_public_id)
                    )
                )
                assert agent is not None and conversation is not None
                inbound = await session.scalar(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.actor == "visitor",
                    )
                    .order_by(ConversationMessage.id.desc())
                )
                assert inbound is not None
                return IntakeActionContext(
                    workspace_id=conversation.workspace_id,
                    agent_id=agent.id,
                    revision_id=conversation.revision_id,
                    conversation_id=conversation.id,
                    source_message_id=inbound.id,
                    channel_connection_id=conversation.channel_connection_id,
                    channel="web",
                )

        action_context = asyncio.run(context())
        keys = {field["semantic"]: field["key"] for field in materialized["fields"]}
        payload = IntakeActionInput(
            answers={
                keys["name"]: "An",
                keys["email"]: "AN@example.com",
                keys["context"]: "Cần tư vấn gói phù hợp",
            }
        )
        service = IntakeActionService(session_factory, settings)

        follow_up = asyncio.run(
            FollowUpActionService(session_factory, settings).request(
                FollowUpActionContext(
                    workspace_id=action_context.workspace_id,
                    agent_id=action_context.agent_id,
                    revision_id=action_context.revision_id,
                    conversation_id=action_context.conversation_id,
                    source_message_id=action_context.source_message_id,
                    channel_connection_id=action_context.channel_connection_id,
                    channel=action_context.channel,
                ),
                FollowUpActionInput(email="an@example.com"),
            )
        )
        assert follow_up.status == "recorded"

        missing = asyncio.run(
            service.submit(
                action_context,
                IntakeActionInput(answers={keys["name"]: "An"}),
            )
        )
        assert missing.status == "needs_information"
        assert set(missing.missing_field_keys) == {keys["email"], keys["context"]}

        recorded = asyncio.run(service.submit(action_context, payload))
        assert recorded.status == "recorded"
        assert recorded.lead_id == follow_up.lead_id
        replay = asyncio.run(service.submit(action_context, payload))
        assert replay.status == "already_recorded"
        assert replay.replayed is True

        conflict = asyncio.run(
            service.submit(
                action_context,
                IntakeActionInput(answers={**payload.answers, keys["context"]: "Nhu cầu khác"}),
            )
        )
        assert conflict.status == "denied"
        assert conflict.safe_code == "IDEMPOTENCY_CONFLICT"

        forged = asyncio.run(service.submit(replace(action_context, workspace_id=uuid4()), payload))
        assert forged.status == "denied"
        assert forged.safe_code == "ACTION_CONTEXT_MISMATCH"

        async def counts() -> tuple[int, int, int]:
            async with session_factory() as session:
                return (
                    int(await session.scalar(select(func.count()).select_from(Lead)) or 0),
                    int(
                        await session.scalar(select(func.count()).select_from(IntakeSubmission))
                        or 0
                    ),
                    int(
                        await session.scalar(
                            select(func.count()).select_from(IntakeActionExecution)
                        )
                        or 0
                    ),
                )

        assert asyncio.run(counts()) == (1, 1, 1)

        listed = owner.get(f"/api/v1/workspaces/{published['workspace_id']}/leads")
        assert listed.status_code == 200, listed.text
        lead = listed.json()["items"][0]
        assert lead["qualification_status"] == "pending_review"
        assert lead["intake"]["purpose"] == "Tư vấn giải pháp phù hợp"

        detail = owner.get(f"/api/v1/workspaces/{published['workspace_id']}/leads/{lead['id']}")
        assert detail.status_code == 200, detail.text
        assert [answer["label"] for answer in detail.json()["intake"]["answers"]] == [
            "Tên khách",
            "Email liên hệ",
            "Nhu cầu",
        ]

        qualified = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/leads/{lead['id']}/qualification",
            json={
                "qualification_status": "qualified",
                "qualification_version": 1,
                "reason": "Nhu cầu phù hợp",
            },
            headers=csrf_headers(owner),
        )
        assert qualified.status_code == 200, qualified.text
        assert qualified.json()["qualification_status"] == "qualified"
        assert qualified.json()["qualification_version"] == 2

        stale = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/leads/{lead['id']}/qualification",
            json={
                "qualification_status": "not_qualified",
                "qualification_version": 1,
            },
            headers=csrf_headers(owner),
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "QUALIFICATION_VERSION_CONFLICT"

        conversation_detail = owner.get(
            f"/api/v1/workspaces/{published['workspace_id']}/conversations/{conversation_public_id}"
        )
        assert conversation_detail.status_code == 200
        assert conversation_detail.json()["intake"]["purpose"] == materialized["purpose"]

        async def expire_intake_records() -> None:
            async with session_factory() as session, session.begin():
                execution = await session.scalar(
                    select(IntakeActionExecution).where(
                        IntakeActionExecution.action_id == recorded.action_id
                    )
                )
                submission = await session.scalar(
                    select(IntakeSubmission).where(
                        IntakeSubmission.public_id == recorded.submission_id
                    )
                )
                assert execution is not None and submission is not None
                expired = datetime.now(UTC) - timedelta(seconds=1)
                execution.retention_until = expired
                submission.retention_until = expired

        asyncio.run(expire_intake_records())
        swept = asyncio.run(
            RetentionSweeper(session_factory, settings, None).run_once(now=datetime.now(UTC))
        )
        assert swept.intake_executions_deleted == 1
        assert swept.intake_submissions_deleted == 1

        async def retained_lead_without_intake() -> tuple[bool, bool, bool]:
            async with session_factory() as session:
                return (
                    await session.scalar(select(Lead.id).where(Lead.id == recorded.lead_id))
                    is not None,
                    await session.scalar(
                        select(IntakeSubmission.id).where(
                            IntakeSubmission.public_id == recorded.submission_id
                        )
                    )
                    is not None,
                    await session.scalar(
                        select(IntakeActionExecution.id).where(
                            IntakeActionExecution.action_id == recorded.action_id
                        )
                    )
                    is not None,
                )

        assert asyncio.run(retained_lead_without_intake()) == (True, False, False)
