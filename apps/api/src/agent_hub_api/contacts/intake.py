from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.agents.schemas import IntakeDefinition, IntakeFieldDefinition
from agent_hub_api.channels.models import ChannelAgentBinding, ChannelConnection
from agent_hub_api.contacts.models import (
    Contact,
    IntakeActionExecution,
    IntakeSubmission,
)
from agent_hub_api.contacts.reachability import (
    ReachableContactValues,
    resolve_reachable_contact,
)
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.leads.models import Lead

INTAKE_ACTION_ID = "contacts.intake.submit"
_SOURCE_MESSAGE_MAX_AGE = timedelta(minutes=15)
_EMAIL_ADAPTER = TypeAdapter(EmailStr)
logger = logging.getLogger("agent_hub_api.intake_actions")


@dataclass(frozen=True, slots=True)
class IntakeActionContext:
    workspace_id: UUID
    agent_id: int
    revision_id: int
    conversation_id: int
    source_message_id: int
    channel_connection_id: int
    channel: Literal["web", "facebook", "zalo"]


class IntakeActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str | list[str]] = Field(max_length=12)

    @field_validator("answers")
    @classmethod
    def bound_answers(cls, value: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
        if len(json.dumps(value, ensure_ascii=False)) > 8_000:
            raise ValueError("Intake answers are too large")
        return value


class IntakeActionResult(BaseModel):
    status: Literal["recorded", "already_recorded", "needs_information", "denied", "failed"]
    action_id: UUID | None = None
    lead_id: int | None = None
    submission_id: UUID | None = None
    replayed: bool = False
    missing_field_keys: list[str] = Field(default_factory=list)
    invalid_field_keys: list[str] = Field(default_factory=list)
    safe_code: str | None = None


class IntakeActionExecutor(Protocol):
    async def submit(
        self,
        context: IntakeActionContext,
        payload: IntakeActionInput,
    ) -> IntakeActionResult: ...


@dataclass(frozen=True, slots=True)
class _ValidatedAnswers:
    values: dict[str, object]
    name: str | None
    email: str | None
    phone: str | None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _canonical_hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _phone(value: str) -> str | None:
    cleaned = " ".join(value.split())
    allowed = set("+0123456789()-. ")
    digits = sum(character.isdigit() for character in cleaned)
    if any(character not in allowed for character in cleaned) or not 7 <= digits <= 15:
        return None
    return cleaned


def _normalize_field(field: IntakeFieldDefinition, value: str | list[str]) -> object | None:
    if field.kind == "multiple_choice":
        if not isinstance(value, list) or not value or len(value) > len(field.options):
            return None
        allowed = {str(option.key) for option in field.options if option.key is not None}
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized or any(item not in allowed for item in normalized):
            return None
        return normalized
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if field.kind == "short_text" and len(cleaned) <= 500:
        return cleaned
    if field.kind == "long_text" and len(cleaned) <= 2_000:
        return cleaned
    if field.kind == "email":
        try:
            return str(_EMAIL_ADAPTER.validate_python(cleaned)).casefold()
        except ValueError:
            return None
    if field.kind == "phone":
        return _phone(cleaned)
    if field.kind == "single_choice":
        allowed = {str(option.key) for option in field.options if option.key is not None}
        return cleaned if cleaned in allowed else None
    if field.kind == "date":
        try:
            return date.fromisoformat(cleaned).isoformat()
        except ValueError:
            return None
    return None


def _validate_answers(
    definition: IntakeDefinition, payload: IntakeActionInput
) -> tuple[_ValidatedAnswers | None, list[str], list[str]]:
    fields = {str(field.key): field for field in definition.fields if field.key is not None}
    invalid = sorted(key for key in payload.answers if key not in fields)
    values: dict[str, object] = {}
    for key, raw_value in payload.answers.items():
        field = fields.get(key)
        if field is None:
            continue
        normalized = _normalize_field(field, raw_value)
        if normalized is None:
            invalid.append(key)
        else:
            values[key] = normalized
    missing = sorted(key for key, field in fields.items() if field.required and key not in values)
    if missing or invalid:
        return None, missing, sorted(set(invalid))
    semantic_values: dict[str, str] = {}
    for key, value in values.items():
        field = fields[key]
        if field.semantic in {"name", "email", "phone"} and isinstance(value, str):
            semantic_values[field.semantic] = value
    return (
        _ValidatedAnswers(
            values=values,
            name=semantic_values.get("name"),
            email=semantic_values.get("email"),
            phone=semantic_values.get("phone"),
        ),
        [],
        [],
    )


class IntakeActionService:
    """Execute the Contacts-owned structured intake in one independent transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def submit(
        self,
        context: IntakeActionContext,
        payload: IntakeActionInput,
    ) -> IntakeActionResult:
        try:
            async with self.session_factory() as session, session.begin():
                return await self._submit(session, context, payload)
        except IntegrityError:
            return await self._replay_after_conflict(context, payload)
        except Exception:
            logger.exception(
                "intake_action_failed workspace_id=%s conversation_id=%s source_message_id=%s",
                context.workspace_id,
                context.conversation_id,
                context.source_message_id,
            )
            return IntakeActionResult(status="failed", safe_code="INTAKE_ACTION_FAILED")

    async def _submit(
        self,
        session: AsyncSession,
        context: IntakeActionContext,
        payload: IntakeActionInput,
    ) -> IntakeActionResult:
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
            return IntakeActionResult(status="denied", safe_code="ACTION_CONTEXT_MISMATCH")
        if connection.lifecycle_state != "active":
            return IntakeActionResult(status="denied", safe_code="ACTION_CONTEXT_EXPIRED")
        if (
            agent.archived_at is not None
            or agent.status != "published"
            or not agent.intake_action_enabled
            or not revision.intake_action_enabled
            or revision.intake_definition_json is None
            or not binding.enabled
            or binding.active_revision_id != revision.id
        ):
            return IntakeActionResult(status="denied", safe_code="ACTION_DISABLED")
        if (
            conversation.lifecycle_state != "active"
            or conversation.handling_mode != "ai"
            or _aware(conversation.retention_until) <= now
        ):
            return IntakeActionResult(status="denied", safe_code="ACTION_CONTEXT_EXPIRED")
        if (
            source_message.actor != "visitor"
            or source_message.direction != "inbound"
            or source_message.status != "completed"
            or now - _aware(source_message.created_at) > _SOURCE_MESSAGE_MAX_AGE
        ):
            return IntakeActionResult(status="denied", safe_code="INVALID_ACTION_EVIDENCE")
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
            return IntakeActionResult(status="denied", safe_code="STALE_ACTION_EVIDENCE")

        definition = IntakeDefinition.model_validate(revision.intake_definition_json)
        if any(field.key is None for field in definition.fields) or any(
            option.key is None for field in definition.fields for option in field.options
        ):
            return IntakeActionResult(status="denied", safe_code="INVALID_INTAKE_DEFINITION")
        validated, missing, invalid = _validate_answers(definition, payload)
        if validated is None:
            return IntakeActionResult(
                status="needs_information",
                missing_field_keys=missing,
                invalid_field_keys=invalid,
                safe_code="INTAKE_VALIDATION_REQUIRED",
            )
        if context.channel == "web" and validated.email is None and validated.phone is None:
            contact_keys = [
                str(field.key)
                for field in definition.fields
                if field.semantic in {"email", "phone"} and field.key is not None
            ]
            return IntakeActionResult(
                status="needs_information",
                missing_field_keys=contact_keys,
                safe_code="WEBSITE_CONTACT_REQUIRED",
            )

        definition_json = definition.model_dump(mode="json")
        definition_hash = _canonical_hash(definition_json)
        digest = _canonical_hash(
            {
                "action": INTAKE_ACTION_ID,
                "workspace_id": str(context.workspace_id),
                "agent_id": context.agent_id,
                "revision_id": context.revision_id,
                "conversation_id": context.conversation_id,
                "source_message_id": context.source_message_id,
                "definition_hash": definition_hash,
                "answers": validated.values,
            }
        )
        existing_execution = (
            await session.scalars(
                select(IntakeActionExecution)
                .where(IntakeActionExecution.source_message_id == source_message.id)
                .with_for_update()
            )
        ).one_or_none()
        if existing_execution is not None:
            return await self._replay(session, existing_execution, digest)
        existing_submission = (
            await session.scalars(
                select(IntakeSubmission)
                .where(IntakeSubmission.conversation_id == conversation.id)
                .with_for_update()
            )
        ).one_or_none()
        if existing_submission is not None:
            if existing_submission.request_hash != digest:
                return IntakeActionResult(status="denied", safe_code="INTAKE_ALREADY_FINALIZED")
            return IntakeActionResult(
                status="already_recorded",
                lead_id=existing_submission.lead_id,
                submission_id=existing_submission.public_id,
                replayed=True,
            )

        contact = await self._reachable_contact(
            session, context, conversation, connection, validated, definition, now
        )
        if contact is None:
            return IntakeActionResult(status="denied", safe_code="CONTACT_UNAVAILABLE")
        retention_until = now + timedelta(days=self.settings.lead_retention_days)
        evidence_retention_until = min(retention_until, _aware(conversation.retention_until))
        execution = IntakeActionExecution(
            action_id=new_uuid_v7(),
            workspace_id=context.workspace_id,
            agent_id=context.agent_id,
            revision_id=context.revision_id,
            conversation_id=context.conversation_id,
            source_message_id=context.source_message_id,
            contact_id=contact.id,
            idempotency_key=f"intake:{context.source_message_id}",
            request_hash=digest,
            state="executing",
            retention_until=evidence_retention_until,
            started_at=now,
        )
        session.add(execution)
        await session.flush()

        lead = (
            await session.scalars(
                select(Lead).where(Lead.conversation_id == conversation.id).with_for_update()
            )
        ).one_or_none()
        if lead is not None and not self._compatible(lead, validated):
            execution.state = "failed_terminal"
            execution.safe_error_code = "IDEMPOTENCY_CONFLICT"
            execution.completed_at = now
            return IntakeActionResult(status="denied", safe_code="IDEMPOTENCY_CONFLICT")
        if lead is None:
            lead = Lead(
                workspace_id=context.workspace_id,
                conversation_id=conversation.id,
                session_id=conversation.session_id if context.channel == "web" else None,
                agent_id=context.agent_id,
                revision_id=context.revision_id,
                contact_id=contact.id,
                name=validated.name,
                normalized_email=validated.email,
                phone=validated.phone,
                source_channel=context.channel,
                capture_source="agent_action",
                consent_at=None,
                consent_text_version=None,
                idempotency_key=f"intake:{context.source_message_id}",
                request_hash=digest,
                followup_status="new",
                qualification_status="pending_review",
                qualification_version=1,
                retention_until=retention_until,
            )
            session.add(lead)
            await session.flush()
        elif lead.qualification_status is None:
            lead.qualification_status = "pending_review"
            lead.qualification_version = 1
            if lead.name is None:
                lead.name = validated.name
            if lead.normalized_email is None:
                lead.normalized_email = validated.email
            if lead.phone is None:
                lead.phone = validated.phone

        submission = IntakeSubmission(
            public_id=new_uuid_v7(),
            workspace_id=context.workspace_id,
            agent_id=context.agent_id,
            revision_id=context.revision_id,
            conversation_id=context.conversation_id,
            source_message_id=context.source_message_id,
            contact_id=contact.id,
            lead_id=lead.id,
            purpose=definition.purpose,
            disclosure_version=cast(str, definition.disclosure_version),
            definition_hash=definition_hash,
            definition_json=definition_json,
            answers_json=validated.values,
            request_hash=digest,
            state="completed",
            retention_until=evidence_retention_until,
            submitted_at=now,
        )
        session.add(submission)
        await session.flush()
        execution.lead_id = lead.id
        execution.submission_id = submission.id
        execution.state = "succeeded"
        execution.safe_outcome = "recorded"
        execution.completed_at = now
        return IntakeActionResult(
            status="recorded",
            action_id=execution.action_id,
            lead_id=lead.id,
            submission_id=submission.public_id,
        )

    async def _reachable_contact(
        self,
        session: AsyncSession,
        context: IntakeActionContext,
        conversation: Conversation,
        connection: ChannelConnection,
        values: _ValidatedAnswers,
        definition: IntakeDefinition,
        now: datetime,
    ) -> Contact | None:
        return await resolve_reachable_contact(
            session,
            self.settings,
            context,
            conversation,
            connection,
            ReachableContactValues(
                name=values.name,
                email=values.email,
                phone=values.phone,
            ),
            website_consent_text_version=cast(str, definition.disclosure_version),
            now=now,
        )

    @staticmethod
    def _compatible(lead: Lead, values: _ValidatedAnswers) -> bool:
        return all(
            proposed is None or existing is None or proposed == existing
            for proposed, existing in (
                (values.name, lead.name),
                (values.email, lead.normalized_email),
                (values.phone, lead.phone),
            )
        )

    @staticmethod
    async def _replay(
        session: AsyncSession, execution: IntakeActionExecution, digest: str
    ) -> IntakeActionResult:
        if execution.request_hash != digest:
            return IntakeActionResult(status="denied", safe_code="IDEMPOTENCY_CONFLICT")
        if execution.state != "succeeded" or execution.submission_id is None:
            return IntakeActionResult(status="denied", safe_code="ACTION_NOT_REPLAYABLE")
        submission = await session.get(IntakeSubmission, execution.submission_id)
        if submission is None or submission.workspace_id != execution.workspace_id:
            return IntakeActionResult(status="failed", safe_code="INTAKE_ACTION_FAILED")
        execution.replay_count += 1
        return IntakeActionResult(
            status="already_recorded",
            action_id=execution.action_id,
            lead_id=execution.lead_id,
            submission_id=submission.public_id,
            replayed=True,
        )

    async def _replay_after_conflict(
        self, context: IntakeActionContext, payload: IntakeActionInput
    ) -> IntakeActionResult:
        async with self.session_factory() as session, session.begin():
            revision = await session.get(AgentRevision, context.revision_id)
            if revision is None or revision.intake_definition_json is None:
                return IntakeActionResult(status="failed", safe_code="INTAKE_ACTION_FAILED")
            definition = IntakeDefinition.model_validate(revision.intake_definition_json)
            validated, _, _ = _validate_answers(definition, payload)
            if validated is None:
                return IntakeActionResult(status="failed", safe_code="INTAKE_ACTION_FAILED")
            digest = _canonical_hash(
                {
                    "action": INTAKE_ACTION_ID,
                    "workspace_id": str(context.workspace_id),
                    "agent_id": context.agent_id,
                    "revision_id": context.revision_id,
                    "conversation_id": context.conversation_id,
                    "source_message_id": context.source_message_id,
                    "definition_hash": _canonical_hash(definition.model_dump(mode="json")),
                    "answers": validated.values,
                }
            )
            execution = (
                await session.scalars(
                    select(IntakeActionExecution)
                    .where(
                        IntakeActionExecution.workspace_id == context.workspace_id,
                        IntakeActionExecution.source_message_id == context.source_message_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if execution is None:
                return IntakeActionResult(status="failed", safe_code="INTAKE_ACTION_FAILED")
            return await self._replay(session, execution, digest)
