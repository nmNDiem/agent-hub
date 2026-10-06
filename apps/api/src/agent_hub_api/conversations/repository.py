from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from agent_hub_api.agents.models import Agent
from agent_hub_api.channels.models import ChannelConnection
from agent_hub_api.conversations.models import Conversation, ConversationMessage
from agent_hub_api.widget.models import VisitorImageUpload

ConversationRow = tuple[Conversation, UUID, str, int, str | None, str]


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base_statement() -> Select[ConversationRow]:
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
        return (
            select(
                Conversation,
                Agent.public_id,
                Agent.name,
                message_count,
                preview,
                ChannelConnection.provider,
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
        active_since: datetime | None = None,
        agent_public_id: UUID | None = None,
        cursor_at: datetime | None = None,
        cursor_public_id: UUID | None = None,
    ) -> list[ConversationRow]:
        statement = self._base_statement().where(Conversation.workspace_id == workspace_id)
        if active_since is not None:
            statement = statement.where(Conversation.last_message_at >= active_since)
        if agent_public_id is not None:
            statement = statement.where(Agent.public_id == agent_public_id)
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

    async def detail(self, workspace_id: UUID, public_id: UUID) -> ConversationRow | None:
        result = await self.session.execute(
            self._base_statement().where(
                Conversation.workspace_id == workspace_id,
                Conversation.public_id == public_id,
            )
        )
        row = result.one_or_none()
        return row._tuple() if row is not None else None

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
