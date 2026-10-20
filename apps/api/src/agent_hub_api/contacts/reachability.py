from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.channels.models import (
    ChannelConnection,
    ChannelThreadMapping,
)
from agent_hub_api.contacts.models import Contact, ContactIdentity
from agent_hub_api.conversations.models import Conversation
from agent_hub_api.core.config import Settings
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.widget.models import WidgetDomain, WidgetSession


class ContactActionContext(Protocol):
    @property
    def workspace_id(self) -> UUID: ...

    @property
    def agent_id(self) -> int: ...

    @property
    def revision_id(self) -> int: ...

    @property
    def channel_connection_id(self) -> int: ...

    @property
    def channel(self) -> Literal["web", "facebook", "zalo"]: ...


@dataclass(frozen=True, slots=True)
class ReachableContactValues:
    name: str | None
    email: str | None
    phone: str | None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def resolve_reachable_contact(
    session: AsyncSession,
    settings: Settings,
    context: ContactActionContext,
    conversation: Conversation,
    connection: ChannelConnection,
    values: ReachableContactValues,
    *,
    website_consent_text_version: str,
    now: datetime,
) -> Contact | None:
    retention_until = now + timedelta(days=settings.lead_retention_days)
    if context.channel == "web":
        contact = await _website_contact(
            session,
            context,
            conversation,
            values,
            website_consent_text_version=website_consent_text_version,
            retention_until=retention_until,
            now=now,
        )
    else:
        contact = await _social_contact(
            session,
            settings,
            context,
            conversation,
            connection,
            values,
            now,
        )
    if contact is None:
        return None
    if _aware(contact.retention_until) < retention_until:
        contact.retention_until = retention_until
    contact.updated_at = now
    return contact


async def _website_contact(
    session: AsyncSession,
    context: ContactActionContext,
    conversation: Conversation,
    values: ReachableContactValues,
    *,
    website_consent_text_version: str,
    retention_until: datetime,
    now: datetime,
) -> Contact | None:
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
            display_name=values.name,
            retention_until=retention_until,
        )
        session.add(contact)
        await session.flush()
        conversation.contact_id = contact.id
    elif contact.workspace_id != context.workspace_id or contact.lifecycle_state != "active":
        return None
    elif values.name is not None and contact.display_name is None:
        contact.display_name = values.name
    await _add_website_identities(
        session,
        contact,
        values,
        website_consent_text_version,
        retention_until,
        now,
    )
    return contact


async def _social_contact(
    session: AsyncSession,
    settings: Settings,
    context: ContactActionContext,
    conversation: Conversation,
    connection: ChannelConnection,
    values: ReachableContactValues,
    now: datetime,
) -> Contact | None:
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
        settings.zalo_response_window_hours
        if context.channel == "zalo"
        else settings.facebook_response_window_hours
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
    if values.name is not None and contact.display_name is None:
        contact.display_name = values.name
    return contact


async def _add_website_identities(
    session: AsyncSession,
    contact: Contact,
    values: ReachableContactValues,
    consent_text_version: str,
    retention_until: datetime,
    now: datetime,
) -> None:
    for identity_type, value in (("email", values.email), ("phone", values.phone)):
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
                    consent_text_version=consent_text_version,
                    retention_until=retention_until,
                )
            )
        elif _aware(identity.retention_until) < retention_until:
            identity.retention_until = retention_until
