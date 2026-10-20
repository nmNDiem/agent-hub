from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.contacts.models import (
    FollowUpActionExecution,
    IntakeActionExecution,
    IntakeSubmission,
)
from agent_hub_api.conversations.models import Conversation
from agent_hub_api.leads.models import Lead

LeadRow = tuple[
    Lead,
    UUID,
    UUID,
    str,
    int,
    str | None,
    int | None,
    IntakeSubmission | None,
    str | None,
    int | None,
]


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def by_session_key(self, session_id: int, idempotency_key: str) -> Lead | None:
        return (
            await self.session.scalars(
                select(Lead).where(
                    Lead.session_id == session_id,
                    Lead.idempotency_key == idempotency_key,
                )
            )
        ).one_or_none()

    async def by_conversation(self, conversation_id: int) -> Lead | None:
        return (
            await self.session.scalars(select(Lead).where(Lead.conversation_id == conversation_id))
        ).one_or_none()

    async def list(
        self,
        workspace_id: UUID,
        *,
        limit: int,
        cursor_created_at: datetime | None = None,
        cursor_id: int | None = None,
        followup_status: str | None = None,
    ) -> list[LeadRow]:
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
        statement = (
            select(
                Lead,
                Conversation.public_id,
                Agent.public_id,
                Agent.name,
                AgentRevision.revision_no,
                FollowUpActionExecution.state,
                FollowUpActionExecution.replay_count,
                IntakeSubmission,
                IntakeActionExecution.state,
                IntakeActionExecution.replay_count,
            )
            .join(
                Conversation,
                (Conversation.workspace_id == Lead.workspace_id)
                & (Conversation.id == Lead.conversation_id),
            )
            .join(
                Agent,
                (Agent.workspace_id == Lead.workspace_id) & (Agent.id == Lead.agent_id),
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
            .where(Lead.workspace_id == workspace_id)
        )
        if followup_status is not None:
            statement = statement.where(Lead.followup_status == followup_status)
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    Lead.created_at < cursor_created_at,
                    and_(Lead.created_at == cursor_created_at, Lead.id < cursor_id),
                )
            )
        result = await self.session.execute(
            statement.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit)
        )
        return [row._tuple() for row in result.all()]

    async def get_for_update(self, workspace_id: UUID, lead_id: int) -> Lead | None:
        return (
            await self.session.scalars(
                select(Lead)
                .where(Lead.workspace_id == workspace_id, Lead.id == lead_id)
                .with_for_update()
            )
        ).one_or_none()

    async def detail(self, workspace_id: UUID, lead_id: int) -> LeadRow | None:
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
        result = await self.session.execute(
            select(
                Lead,
                Conversation.public_id,
                Agent.public_id,
                Agent.name,
                AgentRevision.revision_no,
                FollowUpActionExecution.state,
                FollowUpActionExecution.replay_count,
                IntakeSubmission,
                IntakeActionExecution.state,
                IntakeActionExecution.replay_count,
            )
            .join(
                Conversation,
                (Conversation.workspace_id == Lead.workspace_id)
                & (Conversation.id == Lead.conversation_id),
            )
            .join(
                Agent,
                (Agent.workspace_id == Lead.workspace_id) & (Agent.id == Lead.agent_id),
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
            .where(Lead.workspace_id == workspace_id, Lead.id == lead_id)
        )
        row = result.one_or_none()
        return row._tuple() if row is not None else None
