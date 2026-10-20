from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelThreadMapping,
)
from agent_hub_api.contacts.models import Contact, ContactIdentity, FollowUpActionExecution
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.leads.models import Lead
from agent_hub_api.widget.models import WidgetDomain, WidgetSession

FOLLOW_UP_ACTION_ID = "contacts.follow_up.request"
_SOURCE_MESSAGE_MAX_AGE = timedelta(minutes=15)
logger = logging.getLogger("agent_hub_api.follow_up_actions")


@dataclass(frozen=True, slots=True)
class FollowUpActionContext:
    workspace_id: UUID
    agent_id: int
    revision_id: int
    conversation_id: int
    source_message_id: int
    channel_connection_id: int
    channel: Literal["web", "facebook", "zalo"]


class FollowUpActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("name", "phone", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            return cleaned or None
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = set("+0123456789()-. ")
        digits = sum(character.isdigit() for character in value)
        if any(character not in allowed for character in value) or not 7 <= digits <= 15:
            raise ValueError("Phone number is invalid")
        return value


class FollowUpActionResult(BaseModel):
    status: Literal["recorded", "already_recorded", "needs_information", "denied", "failed"]
    action_id: UUID | None = None
    lead_id: int | None = None
    followup_status: Literal["new", "contacted", "closed"] | None = None
    replayed: bool = False
    safe_code: str | None = None


class FollowUpActionExecutor(Protocol):
    async def request(
        self,
        context: FollowUpActionContext,
        payload: FollowUpActionInput,
    ) -> FollowUpActionResult: ...


def _request_hash(context: FollowUpActionContext, payload: FollowUpActionInput) -> str:
    canonical = json.dumps(
        {
            "action": FOLLOW_UP_ACTION_ID,
            "workspace_id": str(context.workspace_id),
            "agent_id": context.agent_id,
            "revision_id": context.revision_id,
            "conversation_id": context.conversation_id,
            "source_message_id": context.source_message_id,
            "channel": context.channel,
            "name": payload.name,
            "email": str(payload.email).casefold() if payload.email is not None else None,
            "phone": payload.phone,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class FollowUpActionService:
    """Execute the Contacts-owned action in an independent atomic transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def request(
        self,
        context: FollowUpActionContext,
        payload: FollowUpActionInput,
    ) -> FollowUpActionResult:
        digest = _request_hash(context, payload)
        try:
            async with self.session_factory() as session, session.begin():
                return await self._request(session, context, payload, digest)
        except IntegrityError:
            return await self._replay_after_conflict(context, digest)
        except Exception:
            logger.exception(
                "follow_up_action_failed workspace_id=%s conversation_id=%s source_message_id=%s",
                context.workspace_id,
                context.conversation_id,
                context.source_message_id,
            )
            return FollowUpActionResult(status="failed", safe_code="FOLLOW_UP_ACTION_FAILED")

    async def _request(
        self,
        session: AsyncSession,
        context: FollowUpActionContext,
        payload: FollowUpActionInput,
        digest: str,
    ) -> FollowUpActionResult:
        now = datetime.now(UTC)
        conversation = (
            await session.scalars(
                select(Conversation)
                .where(
                    Conversation.id == context.conversation_id,
                    Conversation.workspace_id == context.workspace_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        agent = await session.get(Agent, context.agent_id)
        revision = await session.get(AgentRevision, context.revision_id)
        source_message = await session.get(ConversationMessage, context.source_message_id)
        connection = await session.get(ChannelConnection, context.channel_connection_id)
        binding = (
            await session.scalars(
                select(ChannelAgentBinding).where(
                    ChannelAgentBinding.workspace_id == context.workspace_id,
                    ChannelAgentBinding.connection_id == context.channel_connection_id,
                    ChannelAgentBinding.agent_id == context.agent_id,
                )
            )
        ).one_or_none()
        if (
            conversation is None
            or agent is None
            or revision is None
            or source_message is None
            or connection is None
            or binding is None
            or agent.workspace_id != context.workspace_id
            or revision.workspace_id != context.workspace_id
            or revision.agent_id != context.agent_id
            or conversation.agent_id != context.agent_id
            or conversation.revision_id != context.revision_id
            or conversation.channel_connection_id != context.channel_connection_id
            or source_message.workspace_id != context.workspace_id
            or source_message.conversation_id != context.conversation_id
            or connection.workspace_id != context.workspace_id
            or connection.provider != context.channel
        ):
            return FollowUpActionResult(status="denied", safe_code="ACTION_CONTEXT_MISMATCH")
        if connection.lifecycle_state != "active":
            return FollowUpActionResult(status="denied", safe_code="ACTION_CONTEXT_EXPIRED")
        if (
            agent.archived_at is not None
            or agent.status != "published"
            or not agent.follow_up_action_enabled
            or not revision.follow_up_action_enabled
            or not binding.enabled
            or binding.active_revision_id != revision.id
        ):
            return FollowUpActionResult(status="denied", safe_code="ACTION_DISABLED")
        if (
            conversation.lifecycle_state != "active"
            or conversation.handling_mode != "ai"
            or _aware(conversation.retention_until) <= now
        ):
            return FollowUpActionResult(status="denied", safe_code="ACTION_CONTEXT_EXPIRED")
        if (
            source_message.actor != "visitor"
            or source_message.direction != "inbound"
            or source_message.status != "completed"
            or now - _aware(source_message.created_at) > _SOURCE_MESSAGE_MAX_AGE
        ):
            return FollowUpActionResult(status="denied", safe_code="INVALID_ACTION_EVIDENCE")
        latest_inbound = await session.scalar(
            select(func.max(ConversationMessage.id)).where(
                ConversationMessage.workspace_id == context.workspace_id,
                ConversationMessage.conversation_id == context.conversation_id,
                ConversationMessage.actor == "visitor",
                ConversationMessage.direction == "inbound",
                ConversationMessage.status == "completed",
            )
        )
        if latest_inbound != source_message.id:
            return FollowUpActionResult(status="denied", safe_code="STALE_ACTION_EVIDENCE")
        if context.channel == "web" and payload.email is None and payload.phone is None:
            return FollowUpActionResult(
                status="needs_information", safe_code="WEBSITE_CONTACT_REQUIRED"
            )

        existing_execution = (
            await session.scalars(
                select(FollowUpActionExecution)
                .where(FollowUpActionExecution.source_message_id == source_message.id)
                .with_for_update()
            )
        ).one_or_none()
        if existing_execution is not None:
            return self._replay(existing_execution, digest)

        contact = await self._reachable_contact(
            session, context, conversation, connection, payload, now
        )
        if contact is None:
            return FollowUpActionResult(status="denied", safe_code="CONTACT_UNAVAILABLE")

        retention_until = now + timedelta(days=self.settings.lead_retention_days)
        evidence_retention_until = min(retention_until, _aware(conversation.retention_until))
        execution = FollowUpActionExecution(
            action_id=new_uuid_v7(),
            workspace_id=context.workspace_id,
            agent_id=context.agent_id,
            revision_id=context.revision_id,
            conversation_id=context.conversation_id,
            source_message_id=context.source_message_id,
            contact_id=contact.id,
            idempotency_key=f"follow-up:{context.source_message_id}",
            request_hash=digest,
            state="executing",
            retention_until=evidence_retention_until,
            started_at=now,
        )
        session.add(execution)
        await session.flush()

        lead = (
            await session.scalars(
                select(Lead)
                .where(Lead.conversation_id == conversation.id)
                .with_for_update()
            )
        ).one_or_none()
        if lead is not None:
            if not self._compatible(lead, payload):
                execution.state = "failed_terminal"
                execution.safe_error_code = "IDEMPOTENCY_CONFLICT"
                execution.completed_at = now
                return FollowUpActionResult(status="denied", safe_code="IDEMPOTENCY_CONFLICT")
            execution.lead_id = lead.id
            execution.state = "succeeded"
            execution.safe_outcome = "already_recorded"
            execution.replay_count = 1
            execution.completed_at = now
            return FollowUpActionResult(
                status="already_recorded",
                action_id=execution.action_id,
                lead_id=lead.id,
                followup_status=cast(Literal["new", "contacted", "closed"], lead.followup_status),
                replayed=True,
            )

        normalized_email = (
            str(payload.email).casefold() if payload.email is not None else None
        )
        lead = Lead(
            workspace_id=context.workspace_id,
            conversation_id=conversation.id,
            session_id=conversation.session_id if context.channel == "web" else None,
            agent_id=context.agent_id,
            revision_id=context.revision_id,
            contact_id=contact.id,
            name=payload.name,
            normalized_email=normalized_email,
            phone=payload.phone,
            source_channel=context.channel,
            capture_source="agent_action",
            consent_at=None,
            consent_text_version=None,
            idempotency_key=f"follow-up:{context.source_message_id}",
            request_hash=digest,
            followup_status="new",
            retention_until=retention_until,
        )
        session.add(lead)
        await session.flush()
        execution.lead_id = lead.id
        execution.state = "succeeded"
        execution.safe_outcome = "recorded"
        execution.completed_at = now
        return FollowUpActionResult(
            status="recorded",
            action_id=execution.action_id,
            lead_id=lead.id,
            followup_status="new",
        )

    async def _reachable_contact(
        self,
        session: AsyncSession,
        context: FollowUpActionContext,
        conversation: Conversation,
        connection: ChannelConnection,
        payload: FollowUpActionInput,
        now: datetime,
    ) -> Contact | None:
        retention_until = now + timedelta(days=self.settings.lead_retention_days)
        if context.channel == "web":
            if conversation.session_id is None:
                return None
            widget_session = await session.get(WidgetSession, conversation.session_id)
            if (
                widget_session is None
                or widget_session.workspace_id != context.workspace_id
                or widget_session.agent_id != context.agent_id
                or widget_session.revision_id != context.revision_id
                or widget_session.channel_id != context.channel_connection_id
                or widget_session.revoked_at is not None
                or _aware(widget_session.expires_at) <= now
            ):
                return None
            allowed_origin = await session.scalar(
                select(WidgetDomain.id).where(
                    WidgetDomain.workspace_id == context.workspace_id,
                    WidgetDomain.channel_id == context.channel_connection_id,
                    WidgetDomain.normalized_origin == widget_session.normalized_origin,
                )
            )
            if allowed_origin is None:
                return None
            contact = (
                await session.get(Contact, conversation.contact_id, with_for_update=True)
                if conversation.contact_id is not None
                else None
            )
            if contact is None:
                contact = Contact(
                    public_id=new_uuid_v7(),
                    workspace_id=context.workspace_id,
                    display_name=payload.name,
                    retention_until=retention_until,
                )
                session.add(contact)
                await session.flush()
                conversation.contact_id = contact.id
            elif (
                contact.workspace_id != context.workspace_id
                or contact.lifecycle_state != "active"
            ):
                return None
            elif payload.name is not None and contact.display_name is None:
                contact.display_name = payload.name
            await self._add_website_identities(session, contact, payload, retention_until, now)
        else:
            if (
                connection.lifecycle_state != "active"
                or connection.health_state != "healthy"
                or conversation.contact_id is None
            ):
                return None
            thread = (
                await session.scalars(
                    select(ChannelThreadMapping).where(
                        ChannelThreadMapping.workspace_id == context.workspace_id,
                        ChannelThreadMapping.connection_id == connection.id,
                        ChannelThreadMapping.conversation_id == conversation.id,
                    )
                )
            ).one_or_none()
            window_hours = (
                self.settings.zalo_response_window_hours
                if context.channel == "zalo"
                else self.settings.facebook_response_window_hours
            )
            if (
                thread is None
                or thread.automation_state != "opted_in"
                or thread.last_inbound_at is None
                or _aware(thread.last_inbound_at) < now - timedelta(hours=window_hours)
            ):
                return None
            identity = await session.scalar(
                select(ContactIdentity.id).where(
                    ContactIdentity.workspace_id == context.workspace_id,
                    ContactIdentity.contact_id == conversation.contact_id,
                    ContactIdentity.connection_id == connection.id,
                    ContactIdentity.provider == context.channel,
                    ContactIdentity.identity_type == "channel",
                    ContactIdentity.verification_state == "provider_asserted",
                )
            )
            if identity is None:
                return None
            contact = await session.get(Contact, conversation.contact_id, with_for_update=True)
            if (
                contact is None
                or contact.workspace_id != context.workspace_id
                or contact.lifecycle_state != "active"
            ):
                return None
            if payload.name is not None and contact.display_name is None:
                contact.display_name = payload.name
        if _aware(contact.retention_until) < retention_until:
            contact.retention_until = retention_until
        contact.updated_at = now
        return contact

    async def _add_website_identities(
        self,
        session: AsyncSession,
        contact: Contact,
        payload: FollowUpActionInput,
        retention_until: datetime,
        now: datetime,
    ) -> None:
        values = (
            ("email", str(payload.email).casefold() if payload.email is not None else None),
            ("phone", payload.phone),
        )
        for identity_type, value in values:
            if value is None:
                continue
            identity = (
                await session.scalars(
                    select(ContactIdentity).where(
                        ContactIdentity.workspace_id == contact.workspace_id,
                        ContactIdentity.contact_id == contact.id,
                        ContactIdentity.provider == "website",
                        ContactIdentity.identity_type == identity_type,
                        ContactIdentity.normalized_value == value,
                    )
                )
            ).one_or_none()
            if identity is None:
                session.add(
                    ContactIdentity(
                        workspace_id=contact.workspace_id,
                        contact_id=contact.id,
                        provider="website",
                        identity_type=identity_type,
                        normalized_value=value,
                        verification_state="consented",
                        consent_at=now,
                        consent_text_version="conversation-explicit-follow-up-v1",
                        retention_until=retention_until,
                    )
                )
            elif _aware(identity.retention_until) < retention_until:
                identity.retention_until = retention_until

    @staticmethod
    def _compatible(lead: Lead, payload: FollowUpActionInput) -> bool:
        email = str(payload.email).casefold() if payload.email is not None else None
        comparisons = (
            (payload.name, lead.name),
            (email, lead.normalized_email),
            (payload.phone, lead.phone),
        )
        return all(proposed is None or proposed == existing for proposed, existing in comparisons)

    @staticmethod
    def _replay(execution: FollowUpActionExecution, digest: str) -> FollowUpActionResult:
        if execution.request_hash != digest:
            return FollowUpActionResult(status="denied", safe_code="IDEMPOTENCY_CONFLICT")
        if execution.state != "succeeded" or execution.lead_id is None:
            return FollowUpActionResult(status="denied", safe_code="ACTION_NOT_REPLAYABLE")
        execution.replay_count += 1
        return FollowUpActionResult(
            status="already_recorded",
            action_id=execution.action_id,
            lead_id=execution.lead_id,
            followup_status=None,
            replayed=True,
        )

    async def _replay_after_conflict(
        self, context: FollowUpActionContext, digest: str
    ) -> FollowUpActionResult:
        async with self.session_factory() as session, session.begin():
            execution = (
                await session.scalars(
                    select(FollowUpActionExecution)
                    .where(
                        FollowUpActionExecution.workspace_id == context.workspace_id,
                        FollowUpActionExecution.source_message_id == context.source_message_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if execution is None:
                return FollowUpActionResult(status="failed", safe_code="FOLLOW_UP_ACTION_FAILED")
            return self._replay(execution, digest)
