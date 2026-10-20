from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.contacts.models import (
    Contact,
    ContactIdentity,
    ContactMergeEvent,
    ContactNote,
    ContactTagLink,
    FollowUpActionExecution,
)
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.core.config import Settings
from agent_hub_api.leads.models import Lead
from agent_hub_api.telemetry.models import UsageEvent
from agent_hub_api.widget.image_storage import (
    VisitorImageStorage,
    VisitorImageStorageError,
)
from agent_hub_api.widget.models import (
    VisitorImageUpload,
    WidgetCatalogImageGrant,
    WidgetRateWindow,
    WidgetSession,
)


@dataclass(frozen=True, slots=True)
class RetentionSweepResult:
    follow_up_executions_deleted: int = 0
    sessions_revoked: int = 0
    conversations_revoked: int = 0
    leads_deleted: int = 0
    contacts_expired: int = 0
    grants_deleted: int = 0
    rate_windows_deleted: int = 0
    images_deleted: int = 0
    image_cleanup_failed: int = 0
    conversations_deleted: int = 0
    sessions_deleted: int = 0


class RetentionSweeper:
    """Revoke expired visitor data first, then perform bounded physical cleanup."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        storage: VisitorImageStorage | None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.storage = storage

    async def run_once(
        self,
        *,
        now: datetime | None = None,
        batch_size: int | None = None,
    ) -> RetentionSweepResult:
        sweep_time = now or datetime.now(UTC)
        if sweep_time.tzinfo is None:
            raise ValueError("Retention sweep time must be timezone-aware")
        limit = batch_size or self.settings.retention_sweep_batch_size
        if limit < 1:
            raise ValueError("Retention sweep batch size must be positive")

        follow_up_executions_deleted = await self._delete_expired_follow_up_executions(
            sweep_time, limit
        )
        sessions_revoked = await self._revoke_sessions(sweep_time, limit)
        conversations_revoked = await self._revoke_conversations(sweep_time, limit)
        leads_deleted = await self._delete_expired_leads(sweep_time, limit)
        contacts_expired = await self._expire_contacts(sweep_time, limit)
        grants_deleted = await self._delete_expired_grants(sweep_time, limit)
        rate_windows_deleted = await self._delete_rate_windows(sweep_time, limit)
        images_deleted, image_cleanup_failed = await self._cleanup_images(sweep_time, limit)
        conversations_deleted = await self._delete_conversation_tombstones(limit)
        sessions_deleted = await self._delete_session_tombstones(sweep_time, limit)
        return RetentionSweepResult(
            follow_up_executions_deleted=follow_up_executions_deleted,
            sessions_revoked=sessions_revoked,
            conversations_revoked=conversations_revoked,
            leads_deleted=leads_deleted,
            contacts_expired=contacts_expired,
            grants_deleted=grants_deleted,
            rate_windows_deleted=rate_windows_deleted,
            images_deleted=images_deleted,
            image_cleanup_failed=image_cleanup_failed,
            conversations_deleted=conversations_deleted,
            sessions_deleted=sessions_deleted,
        )

    async def _delete_expired_follow_up_executions(
        self, now: datetime, limit: int
    ) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(FollowUpActionExecution.id)
                    .where(FollowUpActionExecution.retention_until <= now)
                    .order_by(
                        FollowUpActionExecution.retention_until,
                        FollowUpActionExecution.id,
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(
                    delete(FollowUpActionExecution).where(
                        FollowUpActionExecution.id.in_(ids)
                    )
                )
            return len(ids)

    async def _revoke_sessions(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(WidgetSession.id)
                    .where(
                        WidgetSession.expires_at <= now,
                        WidgetSession.revoked_at.is_(None),
                    )
                    .order_by(WidgetSession.expires_at, WidgetSession.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(
                    update(WidgetSession).where(WidgetSession.id.in_(ids)).values(revoked_at=now)
                )
            return len(ids)

    async def _revoke_conversations(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(Conversation.id)
                    .where(
                        Conversation.lifecycle_state == "active",
                        Conversation.retention_until <= now,
                    )
                    .order_by(Conversation.retention_until, Conversation.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if not ids:
                return 0
            await session.execute(
                update(Conversation)
                .where(Conversation.id.in_(ids))
                .values(lifecycle_state="deleted")
            )
            await session.execute(
                delete(FollowUpActionExecution).where(
                    FollowUpActionExecution.conversation_id.in_(ids)
                )
            )
            await session.execute(
                delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(ids))
            )
            await session.execute(
                update(VisitorImageUpload)
                .where(
                    VisitorImageUpload.attached_conversation_id.in_(ids),
                    VisitorImageUpload.status != "deleted",
                )
                .values(
                    status="cleanup_pending",
                    analysis_json=None,
                    last_cleanup_error=None,
                    updated_at=now,
                )
            )
            return len(ids)

    async def _delete_expired_leads(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(Lead.id)
                    .where(Lead.retention_until <= now)
                    .order_by(Lead.retention_until, Lead.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(
                    delete(FollowUpActionExecution).where(
                        FollowUpActionExecution.lead_id.in_(ids)
                    )
                )
                await session.execute(delete(Lead).where(Lead.id.in_(ids)))
            return len(ids)

    async def _expire_contacts(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(Contact.id)
                    .where(
                        Contact.lifecycle_state.in_(["active", "merged"]),
                        Contact.retention_until <= now,
                    )
                    .order_by(Contact.retention_until, Contact.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if not ids:
                return 0
            await session.execute(
                delete(ContactIdentity).where(ContactIdentity.contact_id.in_(ids))
            )
            await session.execute(delete(ContactNote).where(ContactNote.contact_id.in_(ids)))
            await session.execute(delete(ContactTagLink).where(ContactTagLink.contact_id.in_(ids)))
            await session.execute(
                update(ContactMergeEvent)
                .where(
                    or_(
                        ContactMergeEvent.source_contact_id.in_(ids),
                        ContactMergeEvent.target_contact_id.in_(ids),
                    )
                )
                .values(reason="retention_expired")
            )
            await session.execute(
                update(Contact)
                .where(Contact.id.in_(ids))
                .values(
                    display_name=None,
                    assigned_member_id=None,
                    lifecycle_state="expired",
                    merged_into_contact_id=None,
                    state_version=Contact.state_version + 1,
                    updated_at=now,
                )
            )
            return len(ids)

    async def _delete_expired_grants(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(WidgetCatalogImageGrant.id)
                    .where(WidgetCatalogImageGrant.expires_at <= now)
                    .order_by(WidgetCatalogImageGrant.expires_at, WidgetCatalogImageGrant.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(
                    delete(WidgetCatalogImageGrant).where(WidgetCatalogImageGrant.id.in_(ids))
                )
            return len(ids)

    async def _delete_rate_windows(self, now: datetime, limit: int) -> int:
        cutoff = now - timedelta(hours=self.settings.retention_rate_window_hours)
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(WidgetRateWindow.id)
                    .where(WidgetRateWindow.window_started_at <= cutoff)
                    .order_by(WidgetRateWindow.window_started_at, WidgetRateWindow.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(delete(WidgetRateWindow).where(WidgetRateWindow.id.in_(ids)))
            return len(ids)

    async def _cleanup_images(self, now: datetime, limit: int) -> tuple[int, int]:
        async with self.session_factory() as session, session.begin():
            rows = list(
                (
                    await session.execute(
                        select(VisitorImageUpload.id, VisitorImageUpload.object_key)
                        .where(
                            VisitorImageUpload.object_key.is_not(None),
                            or_(
                                VisitorImageUpload.status == "cleanup_pending",
                                VisitorImageUpload.expires_at <= now,
                            ),
                            VisitorImageUpload.status != "deleted",
                        )
                        .order_by(VisitorImageUpload.expires_at, VisitorImageUpload.id)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            ids = [row.id for row in rows]
            if ids:
                await session.execute(
                    update(VisitorImageUpload)
                    .where(VisitorImageUpload.id.in_(ids))
                    .values(
                        status="cleanup_pending",
                        analysis_json=None,
                        last_cleanup_error=None,
                        updated_at=now,
                    )
                )

        deleted_count = 0
        failed_count = 0
        for image_id, object_key in rows:
            if object_key is None:
                continue
            if self.storage is None:
                await self._record_image_failure(image_id, now, "storage_unconfigured")
                failed_count += 1
                continue
            try:
                await self.storage.delete(object_key=object_key)
            except VisitorImageStorageError:
                await self._record_image_failure(image_id, now, "storage_delete_failed")
                failed_count += 1
                continue
            async with self.session_factory() as session, session.begin():
                result = await session.execute(
                    delete(VisitorImageUpload).where(
                        VisitorImageUpload.id == image_id,
                        VisitorImageUpload.status == "cleanup_pending",
                        VisitorImageUpload.object_key == object_key,
                    )
                )
                deleted_count += cast(Any, result).rowcount or 0

        remaining = max(0, limit - len(rows))
        if remaining:
            async with self.session_factory() as session, session.begin():
                metadata_ids = list(
                    await session.scalars(
                        select(VisitorImageUpload.id)
                        .where(
                            VisitorImageUpload.object_key.is_(None),
                            or_(
                                VisitorImageUpload.status == "deleted",
                                VisitorImageUpload.expires_at <= now,
                            ),
                        )
                        .order_by(VisitorImageUpload.expires_at, VisitorImageUpload.id)
                        .limit(remaining)
                    )
                )
                if metadata_ids:
                    result = await session.execute(
                        delete(VisitorImageUpload).where(VisitorImageUpload.id.in_(metadata_ids))
                    )
                    deleted_count += cast(Any, result).rowcount or 0
        return deleted_count, failed_count

    async def _record_image_failure(self, image_id: int, now: datetime, error_code: str) -> None:
        async with self.session_factory() as session, session.begin():
            await session.execute(
                update(VisitorImageUpload)
                .where(VisitorImageUpload.id == image_id)
                .values(
                    cleanup_attempts=VisitorImageUpload.cleanup_attempts + 1,
                    last_cleanup_error=error_code,
                    updated_at=now,
                )
            )

    async def _delete_conversation_tombstones(self, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(Conversation.id)
                    .where(
                        Conversation.lifecycle_state == "deleted",
                        ~exists().where(Lead.conversation_id == Conversation.id),
                        ~exists().where(
                            VisitorImageUpload.attached_conversation_id == Conversation.id
                        ),
                    )
                    .order_by(Conversation.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if not ids:
                return 0
            await session.execute(
                delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(ids))
            )
            await session.execute(
                update(UsageEvent)
                .where(UsageEvent.conversation_id.in_(ids))
                .values(conversation_id=None)
            )
            await session.execute(delete(Conversation).where(Conversation.id.in_(ids)))
            return len(ids)

    async def _delete_session_tombstones(self, now: datetime, limit: int) -> int:
        async with self.session_factory() as session, session.begin():
            ids = list(
                await session.scalars(
                    select(WidgetSession.id)
                    .where(
                        or_(
                            WidgetSession.expires_at <= now,
                            WidgetSession.revoked_at.is_not(None),
                        ),
                        ~exists().where(Conversation.session_id == WidgetSession.id),
                        ~exists().where(Lead.session_id == WidgetSession.id),
                        ~exists().where(VisitorImageUpload.session_id == WidgetSession.id),
                        ~exists().where(WidgetCatalogImageGrant.session_id == WidgetSession.id),
                    )
                    .order_by(WidgetSession.expires_at, WidgetSession.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if ids:
                await session.execute(delete(WidgetSession).where(WidgetSession.id.in_(ids)))
            return len(ids)
