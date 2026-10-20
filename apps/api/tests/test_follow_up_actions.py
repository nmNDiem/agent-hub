import asyncio
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_leads import (
    AppFactory,
    create_published_agent,
    create_visitor,
    csrf_headers,
    visitor_headers,
)

from agent_hub_api.agents.generation import (
    ModelPermanentError,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
    ModelUsage,
)
from agent_hub_api.agents.models import Agent
from agent_hub_api.agents.runtime import (
    AgentRuntimeBudget,
    AgentRuntimeError,
    GroundedAgentRuntime,
)
from agent_hub_api.channels.models import ChannelConnection
from agent_hub_api.contacts.follow_up import (
    FollowUpActionContext,
    FollowUpActionInput,
    FollowUpActionService,
)
from agent_hub_api.contacts.models import FollowUpActionExecution
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.knowledge.retrieval import RetrievedKnowledge
from agent_hub_api.leads.models import Lead
from agent_hub_api.operations.retention import RetentionSweeper

pytest_plugins = ("test_leads",)


class EmptyKnowledge:
    async def search(self, query: str, *, limit: int) -> list[RetrievedKnowledge]:
        del query, limit
        return []


class ActionThenFailureGateway:
    def __init__(self, responses: Sequence[ModelResponse | Exception]) -> None:
        self.responses = list(responses)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        del request
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def runtime_budget() -> AgentRuntimeBudget:
    return AgentRuntimeBudget(
        max_question_chars=4_000,
        max_history_turns=8,
        max_history_chars=12_000,
        max_knowledge_chunks=5,
        max_knowledge_chars=12_000,
        max_prompt_chars=60_000,
        max_tool_result_chars=24_000,
        max_output_tokens=100,
        max_total_tokens=2_000,
        max_model_calls=5,
        max_tool_calls=4,
        catalog_result_limit=8,
    )


def test_follow_up_execution_schema_excludes_message_and_identity_content() -> None:
    columns = set(FollowUpActionExecution.__table__.columns.keys())
    assert columns.isdisjoint(
        {
            "message_text",
            "email",
            "phone",
            "provider_identity",
            "prompt",
            "tool_arguments",
        }
    )


def test_follow_up_action_snapshots_permission_and_commits_independently(
    app_factory: AppFactory,
) -> None:
    app, session_factory = app_factory()
    settings = Settings(
        app_env="test",
        jwt_signing_key="test-signing-key-with-at-least-32-bytes",
    )
    with TestClient(app) as owner:
        published = create_published_agent(owner, "actions@example.com", "actions")
        enabled = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/agents/"
            f"{published['public_agent_id']}",
            json={"follow_up_action_enabled": True},
            headers=csrf_headers(owner),
        )
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["follow_up_action_enabled"] is True

        old_token, old_conversation_id, _ = create_visitor(
            owner, published["public_agent_id"]
        )
        old_turn = owner.post(
            f"/api/v1/widget/conversations/{old_conversation_id}/messages",
            json={"message": "Vui lòng gọi lại cho tôi."},
            headers=visitor_headers(old_token, "old-revision-turn"),
        )
        assert old_turn.status_code == 200

        republished = owner.post(
            f"{published['base']}/publish", headers=csrf_headers(owner)
        )
        assert republished.status_code == 200, republished.text
        assert republished.json()["active_revision"]["revision_no"] == 2

        token, conversation_public_id, _ = create_visitor(
            owner, published["public_agent_id"]
        )
        turn = owner.post(
            f"/api/v1/widget/conversations/{conversation_public_id}/messages",
            json={"message": "Vui lòng gọi lại cho tôi qua email."},
            headers=visitor_headers(token, "follow-up-turn-0001"),
        )
        assert turn.status_code == 200, turn.text

        async def contexts() -> tuple[FollowUpActionContext, FollowUpActionContext]:
            async with session_factory() as session:
                agent = await session.scalar(
                    select(Agent).where(
                        Agent.public_id == UUID(published["public_agent_id"])
                    )
                )
                assert agent is not None
                values: list[FollowUpActionContext] = []
                for public_id in (old_conversation_id, conversation_public_id):
                    conversation = await session.scalar(
                        select(Conversation).where(
                            Conversation.public_id == UUID(public_id)
                        )
                    )
                    assert conversation is not None
                    inbound = await session.scalar(
                        select(ConversationMessage)
                        .where(
                            ConversationMessage.conversation_id == conversation.id,
                            ConversationMessage.actor == "visitor",
                        )
                        .order_by(ConversationMessage.id.desc())
                    )
                    assert inbound is not None
                    values.append(
                        FollowUpActionContext(
                            workspace_id=conversation.workspace_id,
                            agent_id=agent.id,
                            revision_id=conversation.revision_id,
                            conversation_id=conversation.id,
                            source_message_id=inbound.id,
                            channel_connection_id=conversation.channel_connection_id,
                            channel="web",
                        )
                    )
                return values[0], values[1]

        old_context, context = asyncio.run(contexts())
        service = FollowUpActionService(session_factory, settings)
        old_revision_denied = asyncio.run(
            service.request(
                old_context,
                FollowUpActionInput(email="customer@example.com"),
            )
        )
        assert old_revision_denied.status == "denied"
        assert old_revision_denied.safe_code == "ACTION_DISABLED"

        missing = asyncio.run(service.request(context, FollowUpActionInput()))
        assert missing.status == "needs_information"
        assert missing.safe_code == "WEBSITE_CONTACT_REQUIRED"

        async def set_execution_fence(
            *, handling_mode: str = "ai", connection_state: str = "active", expired: bool = False
        ) -> None:
            async with session_factory() as session, session.begin():
                conversation = await session.get(Conversation, context.conversation_id)
                assert conversation is not None
                connection = await session.get(
                    ChannelConnection, context.channel_connection_id
                )
                assert connection is not None
                conversation.handling_mode = handling_mode
                conversation.retention_until = datetime.now(UTC) + timedelta(
                    seconds=-1 if expired else 3600
                )
                connection.lifecycle_state = connection_state

        asyncio.run(set_execution_fence(handling_mode="human"))
        takeover_denied = asyncio.run(
            service.request(context, FollowUpActionInput(email="customer@example.com"))
        )
        assert takeover_denied.safe_code == "ACTION_CONTEXT_EXPIRED"

        asyncio.run(set_execution_fence(connection_state="revoked"))
        revoked_denied = asyncio.run(
            service.request(context, FollowUpActionInput(email="customer@example.com"))
        )
        assert revoked_denied.safe_code == "ACTION_CONTEXT_EXPIRED"

        asyncio.run(set_execution_fence(expired=True))
        expired_denied = asyncio.run(
            service.request(context, FollowUpActionInput(email="customer@example.com"))
        )
        assert expired_denied.safe_code == "ACTION_CONTEXT_EXPIRED"
        asyncio.run(set_execution_fence())

        recorded = asyncio.run(
            service.request(
                context,
                FollowUpActionInput(
                    name="Khách hàng",
                    email="Customer@Example.com",
                ),
            )
        )
        assert recorded.status == "recorded"
        assert recorded.lead_id is not None

        replay = asyncio.run(
            service.request(
                context,
                FollowUpActionInput(
                    name="Khách hàng",
                    email="customer@example.com",
                ),
            )
        )
        assert replay.status == "already_recorded"
        assert replay.action_id == recorded.action_id
        assert replay.replayed is True

        conflict = asyncio.run(
            service.request(
                context,
                FollowUpActionInput(email="different@example.com"),
            )
        )
        assert conflict.status == "denied"
        assert conflict.safe_code == "IDEMPOTENCY_CONFLICT"

        forged_workspace = asyncio.run(
            service.request(
                replace(context, workspace_id=uuid4()),
                FollowUpActionInput(email="customer@example.com"),
            )
        )
        assert forged_workspace.status == "denied"
        assert forged_workspace.safe_code == "ACTION_CONTEXT_MISMATCH"

        async def counts() -> tuple[int, int, int]:
            async with session_factory() as session:
                return (
                    int(await session.scalar(select(func.count()).select_from(Lead)) or 0),
                    int(
                        await session.scalar(
                            select(func.count()).select_from(FollowUpActionExecution)
                        )
                        or 0
                    ),
                    int(
                        await session.scalar(
                            select(FollowUpActionExecution.replay_count)
                        )
                        or 0
                    ),
                )

        assert asyncio.run(counts()) == (1, 1, 1)

        listed = owner.get(
            f"/api/v1/workspaces/{published['workspace_id']}/leads"
        )
        assert listed.status_code == 200, listed.text
        lead = listed.json()["items"][0]
        assert lead["source_channel"] == "web"
        assert lead["capture_source"] == "agent_action"
        assert lead["revision_no"] == 2
        assert lead["action_status"] == "succeeded"
        assert lead["action_replayed"] is True

        conversation_detail = owner.get(
            f"/api/v1/workspaces/{published['workspace_id']}/conversations/"
            f"{conversation_public_id}"
        )
        assert conversation_detail.status_code == 200, conversation_detail.text
        assert conversation_detail.json()["follow_up"]["lead_id"] == recorded.lead_id

        failure_token, failure_conversation_id, _ = create_visitor(
            owner, published["public_agent_id"]
        )
        failure_turn = owner.post(
            f"/api/v1/widget/conversations/{failure_conversation_id}/messages",
            json={"message": "Hãy liên hệ lại qua failure@example.com."},
            headers=visitor_headers(failure_token, "follow-up-failure-turn"),
        )
        assert failure_turn.status_code == 200

        async def failure_context() -> FollowUpActionContext:
            async with session_factory() as session:
                conversation = await session.scalar(
                    select(Conversation).where(
                        Conversation.public_id == UUID(failure_conversation_id)
                    )
                )
                assert conversation is not None
                inbound = await session.scalar(
                    select(ConversationMessage)
                    .where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.actor == "visitor",
                    )
                    .order_by(ConversationMessage.id.desc())
                )
                assert inbound is not None
                return FollowUpActionContext(
                    workspace_id=conversation.workspace_id,
                    agent_id=conversation.agent_id,
                    revision_id=conversation.revision_id,
                    conversation_id=conversation.id,
                    source_message_id=inbound.id,
                    channel_connection_id=conversation.channel_connection_id,
                    channel="web",
                )

        bound_failure_context = asyncio.run(failure_context())
        gateway = ActionThenFailureGateway(
            [
                ModelResponse(
                    content=None,
                    tool_calls=(
                        ModelToolCall(
                            id="persist-before-failure",
                            name="request_human_follow_up",
                            arguments_json=json.dumps({"email": "failure@example.com"}),
                        ),
                    ),
                    usage=ModelUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                ),
                ModelPermanentError("simulated post-action model failure"),
            ]
        )
        runtime = GroundedAgentRuntime(
            gateway=gateway,
            catalog_tools=None,
            knowledge_searcher=EmptyKnowledge(),
            budget=runtime_budget(),
            locale="vi",
            safe_instructions=None,
            follow_up_action_service=service,
            follow_up_action_context=bound_failure_context,
        )
        with pytest.raises(AgentRuntimeError, match="Mình chưa kiểm tra"):
            asyncio.run(runtime.run("Hãy liên hệ lại qua failure@example.com."))

        async def failure_lead_exists() -> bool:
            async with session_factory() as session:
                conversation = await session.scalar(
                    select(Conversation).where(
                        Conversation.public_id == UUID(failure_conversation_id)
                    )
                )
                assert conversation is not None
                return (
                    await session.scalar(
                        select(Lead.id).where(Lead.conversation_id == conversation.id)
                    )
                    is not None
                )

        assert asyncio.run(failure_lead_exists()) is True

        disabled = owner.patch(
            f"/api/v1/workspaces/{published['workspace_id']}/agents/"
            f"{published['public_agent_id']}",
            json={"follow_up_action_enabled": False},
            headers=csrf_headers(owner),
        )
        assert disabled.status_code == 200

        second_turn = owner.post(
            f"/api/v1/widget/conversations/{conversation_public_id}/messages",
            json={"message": "Xin hãy liên hệ lại lần nữa."},
            headers=visitor_headers(token, "follow-up-turn-0002"),
        )
        assert second_turn.status_code == 200
        _, disabled_context = asyncio.run(contexts())
        live_disabled = asyncio.run(
            service.request(
                disabled_context,
                FollowUpActionInput(),
            )
        )
        assert live_disabled.status == "denied"
        assert live_disabled.safe_code == "ACTION_DISABLED"

        async def expire_execution_evidence() -> None:
            async with session_factory() as session, session.begin():
                execution = await session.scalar(
                    select(FollowUpActionExecution).where(
                        FollowUpActionExecution.action_id == recorded.action_id
                    )
                )
                assert execution is not None
                execution.retention_until = datetime.now(UTC) - timedelta(seconds=1)

        asyncio.run(expire_execution_evidence())
        swept = asyncio.run(
            RetentionSweeper(session_factory, settings, None).run_once(
                now=datetime.now(UTC)
            )
        )
        assert swept.follow_up_executions_deleted == 1

        async def retained_outcome_without_evidence() -> tuple[bool, bool]:
            async with session_factory() as session:
                execution_exists = (
                    await session.scalar(
                        select(FollowUpActionExecution.id).where(
                            FollowUpActionExecution.action_id == recorded.action_id
                        )
                    )
                    is not None
                )
                lead_exists = (
                    await session.scalar(select(Lead.id).where(Lead.id == recorded.lead_id))
                    is not None
                )
                return execution_exists, lead_exists

        assert asyncio.run(retained_outcome_without_evidence()) == (False, True)
