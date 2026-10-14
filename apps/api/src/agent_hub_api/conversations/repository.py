from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from agent_hub_api.agents.models import Agent
from agent_hub_api.channels.models import ChannelConnection
from agent_hub_api.conversations.models import (
    Conversation,
    ConversationMessage,
    ConversationNote,
    ConversationReadState,
    ConversationTag,
    ConversationTagLink,
)
from agent_hub_api.identity.models import User
from agent_hub_api.widget.models import VisitorImageUpload
from agent_hub_api.workspaces.models import WorkspaceMember

ConversationRow = tuple[Conversation, UUID, str, int, str | None, str, str | None, int]


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base_statement(member_id: int) -> Select[ConversationRow]:
        message_count = (
            select(func.count(ConversationMessage.id))
            .where(ConversationMessage.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )
        preview = (
            select(ConversationMessage.text)
            .where(
                ConversationMessage.conversation_id == Conversation.id,
                ConversationMessage.actor == "visitor",
                ConversationMessage.status == "completed",
            )
            .order_by(ConversationMessage.sequence_no.desc())
            .limit(1)
            .correlate(Conversation)
            .scalar_subquery()
        )
        assigned_email = (
            select(User.normalized_email)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.id == Conversation.assigned_member_id)
            .correlate(Conversation)
            .scalar_subquery()
        )
        read_sequence = (
            select(ConversationReadState.last_read_sequence)
            .where(
                ConversationReadState.conversation_id == Conversation.id,
                ConversationReadState.member_id == member_id,
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        unread_count = (
            select(func.count(ConversationMessage.id))
            .where(
                ConversationMessage.conversation_id == Conversation.id,
                ConversationMessage.direction == "inbound",
                ConversationMessage.status == "completed",
                ConversationMessage.sequence_no > func.coalesce(read_sequence, 0),
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        return (
            select(
                Conversation,
                Agent.public_id,
                Agent.name,
                message_count,
                preview,
                ChannelConnection.provider,
                assigned_email,
                unread_count,
            )
            .join(
                Agent,
                (Agent.workspace_id == Conversation.workspace_id)
                & (Agent.id == Conversation.agent_id),
            )
            .join(
                ChannelConnection,
                (ChannelConnection.workspace_id == Conversation.workspace_id)
                & (ChannelConnection.id == Conversation.channel_connection_id),
            )
            .where(
                Conversation.lifecycle_state == "active",
                Conversation.last_message_at.is_not(None),
            )
        )

    async def list_rows(
        self,
        workspace_id: UUID,
        *,
        limit: int,
        member_id: int,
        role: str,
        active_since: datetime | None = None,
        agent_public_id: UUID | None = None,
        provider: str | None = None,
        workflow_status: str | None = None,
        assigned_member_id: int | None = None,
        tag_id: int | None = None,
        cursor_at: datetime | None = None,
        cursor_public_id: UUID | None = None,
    ) -> list[ConversationRow]:
        statement = self._base_statement(member_id).where(Conversation.workspace_id == workspace_id)
        if role == "member":
            statement = statement.where(
                or_(
                    Conversation.assigned_member_id.is_(None),
                    Conversation.assigned_member_id == member_id,
                )
            )
        if active_since is not None:
            statement = statement.where(Conversation.last_message_at >= active_since)
        if agent_public_id is not None:
            statement = statement.where(Agent.public_id == agent_public_id)
        if provider is not None:
            statement = statement.where(ChannelConnection.provider == provider)
        if workflow_status is not None:
            statement = statement.where(Conversation.workflow_status == workflow_status)
        if assigned_member_id is not None:
            statement = statement.where(Conversation.assigned_member_id == assigned_member_id)
        if tag_id is not None:
            statement = statement.where(
                select(ConversationTagLink.id)
                .where(
                    ConversationTagLink.workspace_id == workspace_id,
                    ConversationTagLink.conversation_id == Conversation.id,
                    ConversationTagLink.tag_id == tag_id,
                )
                .exists()
            )
        if cursor_at is not None and cursor_public_id is not None:
            statement = statement.where(
                or_(
                    Conversation.last_message_at < cursor_at,
                    and_(
                        Conversation.last_message_at == cursor_at,
                        Conversation.public_id < cursor_public_id,
                    ),
                )
            )
        result = await self.session.execute(
            statement.order_by(
                Conversation.last_message_at.desc(), Conversation.public_id.desc()
            ).limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def detail(
        self,
        workspace_id: UUID,
        public_id: UUID,
        *,
        member_id: int,
        role: str,
        for_update: bool = False,
    ) -> ConversationRow | None:
        statement = self._base_statement(member_id).where(
            Conversation.workspace_id == workspace_id,
            Conversation.public_id == public_id,
        )
        if role == "member":
            statement = statement.where(
                or_(
                    Conversation.assigned_member_id.is_(None),
                    Conversation.assigned_member_id == member_id,
                )
            )
        if for_update:
            statement = statement.with_for_update(of=Conversation)
        result = await self.session.execute(statement)
        row = result.one_or_none()
        return row._tuple() if row is not None else None

    async def member(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        return (
            await self.session.scalars(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
        ).one_or_none()

    async def members(self, workspace_id: UUID) -> list[tuple[WorkspaceMember, str]]:
        result = await self.session.execute(
            select(WorkspaceMember, User.normalized_email)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(User.normalized_email, WorkspaceMember.id)
        )
        return [(member, email) for member, email in result.all()]

    async def tags_for_conversations(
        self, workspace_id: UUID, conversation_ids: list[int]
    ) -> dict[int, list[ConversationTag]]:
        if not conversation_ids:
            return {}
        result = await self.session.execute(
            select(ConversationTagLink.conversation_id, ConversationTag)
            .join(
                ConversationTag,
                (ConversationTag.workspace_id == ConversationTagLink.workspace_id)
                & (ConversationTag.id == ConversationTagLink.tag_id),
            )
            .where(
                ConversationTagLink.workspace_id == workspace_id,
                ConversationTagLink.conversation_id.in_(conversation_ids),
            )
            .order_by(ConversationTag.normalized_name, ConversationTag.id)
        )
        mapped: dict[int, list[ConversationTag]] = {}
        for conversation_id, tag in result.all():
            mapped.setdefault(conversation_id, []).append(tag)
        return mapped

    async def notes(
        self, workspace_id: UUID, conversation_id: int
    ) -> list[tuple[ConversationNote, str]]:
        result = await self.session.execute(
            select(ConversationNote, User.normalized_email)
            .join(WorkspaceMember, WorkspaceMember.id == ConversationNote.author_member_id)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(
                ConversationNote.workspace_id == workspace_id,
                ConversationNote.conversation_id == conversation_id,
            )
            .order_by(ConversationNote.id.desc())
        )
        return [(note, email) for note, email in result.all()]

    async def messages(self, workspace_id: UUID, conversation_id: int) -> list[ConversationMessage]:
        return list(
            await self.session.scalars(
                select(ConversationMessage)
                .where(
                    ConversationMessage.workspace_id == workspace_id,
                    ConversationMessage.conversation_id == conversation_id,
                )
                .order_by(ConversationMessage.sequence_no)
            )
        )

    async def attachments(
        self, workspace_id: UUID, conversation_id: int
    ) -> list[VisitorImageUpload]:
        return list(
            await self.session.scalars(
                select(VisitorImageUpload).where(
                    VisitorImageUpload.workspace_id == workspace_id,
                    VisitorImageUpload.attached_conversation_id == conversation_id,
                    VisitorImageUpload.status == "attached",
                )
            )
        )
