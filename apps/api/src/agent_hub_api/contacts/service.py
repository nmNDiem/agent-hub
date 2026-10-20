from __future__ import annotations

import base64
import csv
import io
import json
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.channels.models import ChannelConnection
from agent_hub_api.contacts.models import (
    Contact,
    ContactAuditEvent,
    ContactIdentity,
    ContactMergeEvent,
    ContactNote,
    ContactTagLink,
    FollowUpActionExecution,
    IntakeActionExecution,
    IntakeSubmission,
)
from agent_hub_api.contacts.repository import ContactRepository, ContactRow
from agent_hub_api.contacts.schemas import (
    ContactActiveMerge,
    ContactDetailResponse,
    ContactDuplicateCandidate,
    ContactIdentityResponse,
    ContactListResponse,
    ContactMergeRequest,
    ContactNoteRequest,
    ContactNoteResponse,
    ContactStateRequest,
    ContactSummary,
    ContactTagRequest,
    ContactTagResponse,
    ContactTimelineItem,
)
from agent_hub_api.conversations.models import Conversation, ConversationTag
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.leads.models import Lead
from agent_hub_api.workspaces.models import WorkspaceMember
from agent_hub_api.workspaces.service import WorkspaceService

ContactProvider = Literal["website", "facebook", "zalo"]


def _encode_cursor(updated_at: datetime, public_id: UUID) -> str:
    payload = json.dumps(
        {"updated_at": updated_at.isoformat(), "public_id": str(public_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        updated_at = datetime.fromisoformat(str(payload["updated_at"]))
        public_id = UUID(str(payload["public_id"]))
        if updated_at.tzinfo is None:
            raise ValueError
        return updated_at, public_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Con trỏ phân trang không hợp lệ.",
        ) from exc


def _csv_cell(value: object | None) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _summary(
    row: ContactRow,
    identities: list[ContactIdentity],
    tags: list[ConversationTag],
) -> ContactSummary:
    contact, assignee_email = row
    channels = sorted({identity.provider for identity in identities})
    return ContactSummary(
        public_id=contact.public_id,
        display_name=contact.display_name,
        lifecycle_state=cast(Literal["active", "expired", "merged"], contact.lifecycle_state),
        state_version=contact.state_version,
        assigned_member_id=contact.assigned_member_id,
        assigned_member_email=assignee_email,
        channels=cast(list[ContactProvider], channels),
        tags=[ContactTagResponse(id=tag.id, name=tag.name) for tag in tags],
        retention_until=contact.retention_until,
        updated_at=contact.updated_at,
    )


class ContactService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = ContactRepository(session)

    async def _access(self, user: User, workspace_id: UUID) -> WorkspaceMember:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        member = (
            await self.session.scalars(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user.id,
                )
            )
        ).one_or_none()
        if member is None or member.role != role:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy cửa hàng.")
        return member

    @staticmethod
    def _can_view(contact: Contact, member: WorkspaceMember) -> bool:
        return member.role != "member" or contact.assigned_member_id in {None, member.id}

    @staticmethod
    def _require_owner_admin(member: WorkspaceMember) -> None:
        if member.role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền thực hiện thao tác này.",
            )

    async def list_contacts(
        self,
        user: User,
        workspace_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        query: str | None,
        assigned_member_id: int | None,
        tag_id: int | None,
    ) -> ContactListResponse:
        member = await self._access(user, workspace_id)
        cursor_at, cursor_public_id = _decode_cursor(cursor)
        cleaned_query = query.strip() if query else None
        rows = await self.repository.list_rows(
            workspace_id,
            member=member,
            limit=limit + 1,
            cursor_at=cursor_at,
            cursor_public_id=cursor_public_id,
            query=cleaned_query,
            assigned_member_id=assigned_member_id,
            tag_id=tag_id,
        )
        page = rows[:limit]
        identities, tags = await self.repository.metadata(workspace_id, [row[0].id for row in page])
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1][0]
            next_cursor = _encode_cursor(last.updated_at, last.public_id)
        return ContactListResponse(
            items=[
                _summary(row, identities.get(row[0].id, []), tags.get(row[0].id, []))
                for row in page
            ],
            next_cursor=next_cursor,
        )

    async def _row_for_member(
        self, workspace_id: UUID, public_id: UUID, member: WorkspaceMember
    ) -> ContactRow:
        row = await self.repository.row(workspace_id, public_id)
        if row is None or not self._can_view(row[0], member):
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy khách hàng.")
        return row

    async def detail(
        self, user: User, workspace_id: UUID, public_id: UUID
    ) -> ContactDetailResponse:
        member = await self._access(user, workspace_id)
        row = await self._row_for_member(workspace_id, public_id, member)
        contact = row[0]
        source_ids = list(
            await self.session.scalars(
                select(Contact.id).where(
                    Contact.workspace_id == workspace_id,
                    Contact.merged_into_contact_id == contact.id,
                    Contact.lifecycle_state == "merged",
                )
            )
        )
        cluster_ids = [contact.id, *source_ids]
        identities_by_contact, tags_by_contact = await self.repository.metadata(
            workspace_id, cluster_ids
        )
        identities = [
            identity
            for contact_id in cluster_ids
            for identity in identities_by_contact.get(contact_id, [])
        ]
        all_tags = {
            tag.id: tag for contact_id in cluster_ids for tag in tags_by_contact.get(contact_id, [])
        }
        summary = _summary(row, identities, list(all_tags.values()))

        note_rows = await self.session.execute(
            select(ContactNote, User.normalized_email)
            .join(
                WorkspaceMember,
                (WorkspaceMember.workspace_id == ContactNote.workspace_id)
                & (WorkspaceMember.id == ContactNote.author_member_id),
            )
            .join(User, User.id == WorkspaceMember.user_id)
            .where(
                ContactNote.workspace_id == workspace_id,
                ContactNote.contact_id.in_(cluster_ids),
            )
            .order_by(ContactNote.created_at.desc(), ContactNote.id.desc())
        )
        notes = [
            ContactNoteResponse(
                id=note.id,
                author_member_id=note.author_member_id,
                author_email=email,
                body=note.body,
                created_at=note.created_at,
            )
            for note, email in note_rows.all()
        ]
        timeline = await self._timeline(workspace_id, cluster_ids, notes)
        duplicates = (
            await self._duplicates(workspace_id, contact.id, identities)
            if member.role in {"owner", "admin"} and contact.lifecycle_state == "active"
            else []
        )
        merge_rows = list(
            await self.session.scalars(
                select(ContactMergeEvent).where(
                    ContactMergeEvent.workspace_id == workspace_id,
                    ContactMergeEvent.target_contact_id == contact.id,
                    ContactMergeEvent.reversed_at.is_(None),
                )
            )
        )
        contact_ids = {
            item_id: item_public_id
            for item_id, item_public_id in (
                await self.session.execute(
                    select(Contact.id, Contact.public_id).where(
                        Contact.workspace_id == workspace_id,
                        Contact.id.in_(
                            {
                                value
                                for merge in merge_rows
                                for value in (merge.source_contact_id, merge.target_contact_id)
                            }
                        ),
                    )
                )
            ).all()
        }
        canonical_public_id = None
        if contact.merged_into_contact_id is not None:
            canonical = await self.repository.by_id(workspace_id, contact.merged_into_contact_id)
            canonical_public_id = canonical.public_id if canonical is not None else None
        return ContactDetailResponse(
            contact=summary,
            canonical_public_id=canonical_public_id,
            identities=[
                ContactIdentityResponse(
                    id=identity.id,
                    provider=cast(ContactProvider, identity.provider),
                    identity_type=cast(
                        Literal["email", "phone", "channel"], identity.identity_type
                    ),
                    value=(
                        identity.normalized_value
                        if identity.identity_type in {"email", "phone"}
                        else None
                    ),
                    verification_state=cast(
                        Literal["consented", "provider_asserted"],
                        identity.verification_state,
                    ),
                    consent_at=identity.consent_at,
                    consent_text_version=identity.consent_text_version,
                    retention_until=identity.retention_until,
                )
                for identity in identities
            ],
            notes=notes,
            timeline=timeline,
            duplicate_candidates=duplicates,
            active_merges=[
                ContactActiveMerge(
                    id=merge.id,
                    source_public_id=contact_ids[merge.source_contact_id],
                    target_public_id=contact_ids[merge.target_contact_id],
                    reason=merge.reason,
                    created_at=merge.created_at,
                )
                for merge in merge_rows
            ],
        )

    async def _timeline(
        self,
        workspace_id: UUID,
        contact_ids: list[int],
        notes: list[ContactNoteResponse],
    ) -> list[ContactTimelineItem]:
        items: list[ContactTimelineItem] = [
            ContactTimelineItem(
                key=f"note:{note.id}",
                kind="note",
                occurred_at=note.created_at,
                title="Đã thêm ghi chú",
                detail=f"Bởi {note.author_email}",
            )
            for note in notes
        ]
        conversation_rows = await self.session.execute(
            select(Conversation, ChannelConnection.provider, Agent.name)
            .join(
                ChannelConnection,
                (ChannelConnection.workspace_id == Conversation.workspace_id)
                & (ChannelConnection.id == Conversation.channel_connection_id),
            )
            .join(
                Agent,
                (Agent.workspace_id == Conversation.workspace_id)
                & (Agent.id == Conversation.agent_id),
            )
            .where(
                Conversation.workspace_id == workspace_id,
                Conversation.contact_id.in_(contact_ids),
                Conversation.lifecycle_state == "active",
            )
        )
        for conversation, provider, agent_name in conversation_rows.all():
            items.append(
                ContactTimelineItem(
                    key=f"conversation:{conversation.id}",
                    kind="conversation",
                    occurred_at=conversation.last_message_at or conversation.created_at,
                    title=f"Hội thoại {provider}",
                    detail=agent_name,
                    conversation_public_id=conversation.public_id,
                )
            )
        latest_execution_id = (
            select(func.max(FollowUpActionExecution.id))
            .where(
                FollowUpActionExecution.workspace_id == Lead.workspace_id,
                FollowUpActionExecution.lead_id == Lead.id,
            )
            .correlate(Lead)
            .scalar_subquery()
        )
        latest_intake_execution_id = (
            select(func.max(IntakeActionExecution.id))
            .where(
                IntakeActionExecution.workspace_id == Lead.workspace_id,
                IntakeActionExecution.lead_id == Lead.id,
            )
            .correlate(Lead)
            .scalar_subquery()
        )
        leads = await self.session.execute(
            select(
                Lead,
                AgentRevision.revision_no,
                FollowUpActionExecution.state,
                FollowUpActionExecution.replay_count,
                IntakeSubmission,
                IntakeActionExecution.state,
                IntakeActionExecution.replay_count,
            )
            .join(
                AgentRevision,
                (AgentRevision.workspace_id == Lead.workspace_id)
                & (AgentRevision.agent_id == Lead.agent_id)
                & (AgentRevision.id == Lead.revision_id),
            )
            .outerjoin(FollowUpActionExecution, FollowUpActionExecution.id == latest_execution_id)
            .outerjoin(
                IntakeSubmission,
                (IntakeSubmission.workspace_id == Lead.workspace_id)
                & (IntakeSubmission.lead_id == Lead.id),
            )
            .outerjoin(
                IntakeActionExecution,
                IntakeActionExecution.id == latest_intake_execution_id,
            )
            .where(Lead.workspace_id == workspace_id, Lead.contact_id.in_(contact_ids))
        )
        for (
            lead,
            revision_no,
            action_state,
            replay_count,
            intake,
            intake_action_state,
            intake_replay_count,
        ) in leads.all():
            items.append(
                ContactTimelineItem(
                    key=f"lead:{lead.id}",
                    kind="lead",
                    occurred_at=lead.updated_at,
                    title="Yêu cầu liên hệ",
                    detail=lead.followup_status,
                    lead_id=lead.id,
                    source_channel=cast(Literal["web", "facebook", "zalo"], lead.source_channel),
                    capture_source=cast(
                        Literal["website_form", "agent_action"], lead.capture_source
                    ),
                    revision_no=revision_no,
                    action_status=cast(
                        Literal["succeeded", "failed_retryable", "failed_terminal"] | None,
                        intake_action_state if intake is not None else action_state,
                    ),
                    action_replayed=bool(
                        intake_replay_count if intake is not None else replay_count
                    ),
                    intake_purpose=intake.purpose if intake is not None else None,
                    qualification_status=cast(
                        Literal["pending_review", "qualified", "not_qualified"] | None,
                        lead.qualification_status,
                    ),
                )
            )
        audits = await self.session.scalars(
            select(ContactAuditEvent).where(
                ContactAuditEvent.workspace_id == workspace_id,
                ContactAuditEvent.contact_id.in_(contact_ids),
            )
        )
        titles = {
            "state_changed": "Đã cập nhật hồ sơ",
            "tag_added": "Đã gắn thẻ",
            "merge_completed": "Đã hợp nhất hồ sơ",
            "merge_reversed": "Đã hoàn tác hợp nhất",
        }
        for audit in audits:
            items.append(
                ContactTimelineItem(
                    key=f"audit:{audit.id}",
                    kind="merge" if audit.event_type.startswith("merge_") else "state",
                    occurred_at=audit.created_at,
                    title=titles.get(audit.event_type, "Đã cập nhật hồ sơ"),
                )
            )
        return sorted(items, key=lambda item: (item.occurred_at, item.key), reverse=True)

    async def _duplicates(
        self,
        workspace_id: UUID,
        contact_id: int,
        identities: list[ContactIdentity],
    ) -> list[ContactDuplicateCandidate]:
        values = {
            (identity.identity_type, identity.normalized_value)
            for identity in identities
            if identity.identity_type in {"email", "phone"}
        }
        if not values:
            return []
        matches = await self.session.execute(
            select(Contact, ContactIdentity.identity_type)
            .join(
                ContactIdentity,
                (ContactIdentity.workspace_id == Contact.workspace_id)
                & (ContactIdentity.contact_id == Contact.id),
            )
            .where(
                Contact.workspace_id == workspace_id,
                Contact.id != contact_id,
                Contact.lifecycle_state == "active",
                or_(
                    *[
                        (ContactIdentity.identity_type == identity_type)
                        & (ContactIdentity.normalized_value == value)
                        for identity_type, value in values
                    ]
                ),
            )
        )
        grouped: dict[int, tuple[Contact, set[str]]] = {}
        for candidate, identity_type in matches.all():
            grouped.setdefault(candidate.id, (candidate, set()))[1].add(identity_type)
        return [
            ContactDuplicateCandidate(
                public_id=candidate.public_id,
                display_name=candidate.display_name,
                matching_identity_types=cast(
                    list[Literal["email", "phone"]], sorted(identity_types)
                ),
            )
            for candidate, identity_types in grouped.values()
        ]

    async def _locked_contact(
        self, workspace_id: UUID, public_id: UUID, member: WorkspaceMember
    ) -> Contact:
        contact = (
            await self.session.scalars(
                select(Contact)
                .where(
                    Contact.workspace_id == workspace_id,
                    Contact.public_id == public_id,
                    Contact.lifecycle_state != "expired",
                )
                .with_for_update()
            )
        ).one_or_none()
        if contact is None or not self._can_view(contact, member):
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy khách hàng.")
        return contact

    async def update_state(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        request: ContactStateRequest,
    ) -> None:
        async with self.session.begin():
            member = await self._access(user, workspace_id)
            contact = await self._locked_contact(workspace_id, public_id, member)
            if contact.lifecycle_state != "active":
                raise ApiError(
                    status.HTTP_409_CONFLICT, "CONTACT_MERGED", "Hồ sơ đã được hợp nhất."
                )
            if contact.state_version != request.state_version:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "STALE_CONTACT",
                    "Hồ sơ vừa được cập nhật. Vui lòng tải lại.",
                )
            target_assignee = contact.assigned_member_id
            if request.clear_assignment:
                target_assignee = None
            elif request.assigned_member_id is not None:
                target_assignee = request.assigned_member_id
            if member.role == "member":
                if target_assignee != member.id or contact.assigned_member_id not in {
                    None,
                    member.id,
                }:
                    raise ApiError(
                        status.HTTP_403_FORBIDDEN,
                        "FORBIDDEN",
                        "Bạn chỉ có thể nhận hồ sơ chưa được phân công.",
                    )
                if request.update_display_name and contact.assigned_member_id != member.id:
                    raise ApiError(
                        status.HTTP_403_FORBIDDEN,
                        "FORBIDDEN",
                        "Hãy nhận hồ sơ trước khi chỉnh sửa.",
                    )
            if target_assignee is not None:
                assignee = await self.session.get(WorkspaceMember, target_assignee)
                if assignee is None or assignee.workspace_id != workspace_id:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "INVALID_ASSIGNEE",
                        "Người phụ trách không hợp lệ.",
                    )
            changes: dict[str, object] = {}
            if contact.assigned_member_id != target_assignee:
                changes["assigned_member_id"] = {
                    "from": contact.assigned_member_id,
                    "to": target_assignee,
                }
                contact.assigned_member_id = target_assignee
            if request.update_display_name and contact.display_name != request.display_name:
                changes["display_name_changed"] = True
                contact.display_name = request.display_name
            if not changes:
                return
            contact.state_version += 1
            contact.updated_at = datetime.now(UTC)
            self.session.add(
                ContactAuditEvent(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    actor_member_id=member.id,
                    event_type="state_changed",
                    details_json=changes,
                )
            )

    async def add_note(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        request: ContactNoteRequest,
    ) -> None:
        async with self.session.begin():
            member = await self._access(user, workspace_id)
            contact = await self._locked_contact(workspace_id, public_id, member)
            if contact.lifecycle_state != "active" or (
                member.role == "member" and contact.assigned_member_id != member.id
            ):
                raise ApiError(
                    status.HTTP_403_FORBIDDEN,
                    "FORBIDDEN",
                    "Hãy nhận hồ sơ trước khi thêm ghi chú.",
                )
            self.session.add(
                ContactNote(
                    workspace_id=workspace_id,
                    contact_id=contact.id,
                    author_member_id=member.id,
                    body=request.body,
                )
            )
            contact.updated_at = datetime.now(UTC)

    async def add_tag(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        request: ContactTagRequest,
    ) -> None:
        normalized = request.name.casefold()
        async with self.session.begin():
            member = await self._access(user, workspace_id)
            contact = await self._locked_contact(workspace_id, public_id, member)
            if contact.lifecycle_state != "active" or (
                member.role == "member" and contact.assigned_member_id != member.id
            ):
                raise ApiError(
                    status.HTTP_403_FORBIDDEN,
                    "FORBIDDEN",
                    "Hãy nhận hồ sơ trước khi gắn thẻ.",
                )
            tag = (
                await self.session.scalars(
                    select(ConversationTag).where(
                        ConversationTag.workspace_id == workspace_id,
                        ConversationTag.normalized_name == normalized,
                    )
                )
            ).one_or_none()
            if tag is None:
                tag = ConversationTag(
                    workspace_id=workspace_id,
                    name=request.name,
                    normalized_name=normalized,
                )
                self.session.add(tag)
                await self.session.flush()
            exists = await self.session.scalar(
                select(ContactTagLink.id).where(
                    ContactTagLink.contact_id == contact.id, ContactTagLink.tag_id == tag.id
                )
            )
            if exists is None:
                self.session.add(
                    ContactTagLink(
                        workspace_id=workspace_id,
                        contact_id=contact.id,
                        tag_id=tag.id,
                    )
                )
                self.session.add(
                    ContactAuditEvent(
                        workspace_id=workspace_id,
                        contact_id=contact.id,
                        actor_member_id=member.id,
                        event_type="tag_added",
                        details_json={"tag_id": tag.id},
                    )
                )
                contact.updated_at = datetime.now(UTC)

    async def merge(
        self,
        user: User,
        workspace_id: UUID,
        target_public_id: UUID,
        request: ContactMergeRequest,
    ) -> int:
        if request.source_public_id == target_public_id:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "INVALID_MERGE",
                "Không thể hợp nhất một hồ sơ vào chính nó.",
            )
        async with self.session.begin():
            member = await self._access(user, workspace_id)
            self._require_owner_admin(member)
            contacts = list(
                await self.session.scalars(
                    select(Contact)
                    .where(
                        Contact.workspace_id == workspace_id,
                        Contact.public_id.in_([target_public_id, request.source_public_id]),
                    )
                    .order_by(Contact.id)
                    .with_for_update()
                )
            )
            by_public_id = {contact.public_id: contact for contact in contacts}
            source = by_public_id.get(request.source_public_id)
            target = by_public_id.get(target_public_id)
            if source is None or target is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy khách hàng.")
            if source.lifecycle_state != "active" or target.lifecycle_state != "active":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "CONTACT_MERGE_CONFLICT",
                    "Chỉ có thể hợp nhất hai hồ sơ đang hoạt động.",
                )
            source_has_children = await self.session.scalar(
                select(Contact.id).where(
                    Contact.workspace_id == workspace_id,
                    Contact.merged_into_contact_id == source.id,
                    Contact.lifecycle_state == "merged",
                )
            )
            if source_has_children is not None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "CONTACT_MERGE_CHAIN_FORBIDDEN",
                    "Hồ sơ nguồn đang là hồ sơ chính của một lần hợp nhất khác.",
                )
            if (
                source.state_version != request.source_state_version
                or target.state_version != request.target_state_version
            ):
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "STALE_CONTACT",
                    "Hồ sơ vừa được cập nhật. Vui lòng tải lại.",
                )
            now = datetime.now(UTC)
            source.lifecycle_state = "merged"
            source.merged_into_contact_id = target.id
            source.state_version += 1
            source.updated_at = now
            target.state_version += 1
            target.updated_at = now
            target.retention_until = max(target.retention_until, source.retention_until)
            event = ContactMergeEvent(
                workspace_id=workspace_id,
                source_contact_id=source.id,
                target_contact_id=target.id,
                actor_member_id=member.id,
                reason=request.reason,
            )
            self.session.add(event)
            self.session.add_all(
                [
                    ContactAuditEvent(
                        workspace_id=workspace_id,
                        contact_id=contact_id,
                        actor_member_id=member.id,
                        event_type="merge_completed",
                        details_json={},
                    )
                    for contact_id in (source.id, target.id)
                ]
            )
            await self.session.flush()
            return event.id

    async def reverse_merge(
        self,
        user: User,
        workspace_id: UUID,
        target_public_id: UUID,
        merge_id: int,
    ) -> None:
        async with self.session.begin():
            member = await self._access(user, workspace_id)
            self._require_owner_admin(member)
            target = await self._locked_contact(workspace_id, target_public_id, member)
            event = (
                await self.session.scalars(
                    select(ContactMergeEvent)
                    .where(
                        ContactMergeEvent.workspace_id == workspace_id,
                        ContactMergeEvent.id == merge_id,
                        ContactMergeEvent.target_contact_id == target.id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if event is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy lần hợp nhất."
                )
            source = (
                await self.session.scalars(
                    select(Contact)
                    .where(
                        Contact.workspace_id == workspace_id,
                        Contact.id == event.source_contact_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if (
                event.reversed_at is not None
                or source is None
                or source.lifecycle_state != "merged"
                or source.merged_into_contact_id != target.id
            ):
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "MERGE_NOT_REVERSIBLE",
                    "Lần hợp nhất này không còn có thể hoàn tác.",
                )
            now = datetime.now(UTC)
            source.lifecycle_state = "active"
            source.merged_into_contact_id = None
            source.state_version += 1
            source.updated_at = now
            target.state_version += 1
            target.updated_at = now
            retention_values = [
                await self.session.scalar(
                    select(func.max(ContactIdentity.retention_until)).where(
                        ContactIdentity.workspace_id == workspace_id,
                        ContactIdentity.contact_id == target.id,
                    )
                ),
                await self.session.scalar(
                    select(func.max(Lead.retention_until)).where(
                        Lead.workspace_id == workspace_id,
                        Lead.contact_id == target.id,
                    )
                ),
                await self.session.scalar(
                    select(func.max(Conversation.retention_until)).where(
                        Conversation.workspace_id == workspace_id,
                        Conversation.contact_id == target.id,
                    )
                ),
                await self.session.scalar(
                    select(func.max(Contact.retention_until)).where(
                        Contact.workspace_id == workspace_id,
                        Contact.merged_into_contact_id == target.id,
                        Contact.lifecycle_state == "merged",
                    )
                ),
            ]
            target.retention_until = max(
                (value for value in retention_values if value is not None),
                default=now,
            )
            event.reversed_at = now
            event.reversed_by_member_id = member.id
            self.session.add_all(
                [
                    ContactAuditEvent(
                        workspace_id=workspace_id,
                        contact_id=contact_id,
                        actor_member_id=member.id,
                        event_type="merge_reversed",
                        details_json={},
                    )
                    for contact_id in (source.id, target.id)
                ]
            )

    async def export_csv(self, user: User, workspace_id: UUID) -> str:
        member = await self._access(user, workspace_id)
        self._require_owner_admin(member)
        rows = await self.repository.list_rows(
            workspace_id,
            member=member,
            limit=self.settings.lead_export_max_rows + 1,
            cursor_at=None,
            cursor_public_id=None,
            query=None,
            assigned_member_id=None,
            tag_id=None,
        )
        if len(rows) > self.settings.lead_export_max_rows:
            raise ApiError(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "EXPORT_TOO_LARGE",
                "Dữ liệu xuất vượt quá giới hạn cho phép.",
            )
        identities, tags = await self.repository.metadata(workspace_id, [row[0].id for row in rows])
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "contact_public_id",
                "display_name",
                "email",
                "phone",
                "channels",
                "assignee",
                "tags",
                "retention_until",
            ]
        )
        for contact, assignee_email in rows:
            contact_identities = identities.get(contact.id, [])
            writer.writerow(
                [
                    _csv_cell(contact.public_id),
                    _csv_cell(contact.display_name),
                    _csv_cell(
                        "; ".join(
                            item.normalized_value
                            for item in contact_identities
                            if item.identity_type == "email"
                        )
                    ),
                    _csv_cell(
                        "; ".join(
                            item.normalized_value
                            for item in contact_identities
                            if item.identity_type == "phone"
                        )
                    ),
                    _csv_cell("; ".join(sorted({item.provider for item in contact_identities}))),
                    _csv_cell(assignee_email),
                    _csv_cell("; ".join(tag.name for tag in tags.get(contact.id, []))),
                    _csv_cell(contact.retention_until.isoformat()),
                ]
            )
        return "\ufeff" + output.getvalue()
