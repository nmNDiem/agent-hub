from datetime import UTC, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.agents.runtime import AgentRuntimeUsage
from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.telemetry.models import UsageEvent, WorkspaceUsageMonth
from agent_hub_api.telemetry.schemas import UsageSummaryResponse
from agent_hub_api.widget.vision import VisionResult
from agent_hub_api.workspaces.models import Workspace
from agent_hub_api.workspaces.service import WorkspaceService

UsageSurface = Literal["widget", "playground"]


def month_bounds(timezone_name: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("Workspace timezone is invalid") from exc
    current = (now or datetime.now(UTC)).astimezone(timezone)
    started_local = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if started_local.month == 12:
        ended_local = started_local.replace(year=started_local.year + 1, month=1)
    else:
        ended_local = started_local.replace(month=started_local.month + 1)
    return started_local.astimezone(UTC), ended_local.astimezone(UTC)


class TelemetryService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def resolve_agent_id(self, workspace_id: UUID, public_agent_id: UUID) -> int:
        agent_id = await self.session.scalar(
            select(Agent.id).where(
                Agent.workspace_id == workspace_id,
                Agent.public_id == public_agent_id,
                Agent.archived_at.is_(None),
            )
        )
        if agent_id is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy chatbot.")
        return agent_id

    async def reserve_generation_turn(self, workspace_id: UUID, agent_id: int) -> None:
        workspace = (
            await self.session.scalars(
                select(Workspace).where(Workspace.id == workspace_id).with_for_update()
            )
        ).one_or_none()
        if workspace is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy cửa hàng.")
        agent_exists = await self.session.scalar(
            select(Agent.id).where(
                Agent.workspace_id == workspace_id,
                Agent.id == agent_id,
                Agent.archived_at.is_(None),
            )
        )
        if agent_exists is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy chatbot.")
        period_started_at, _ = month_bounds(workspace.timezone)
        usage_month = (
            await self.session.scalars(
                select(WorkspaceUsageMonth)
                .where(
                    WorkspaceUsageMonth.workspace_id == workspace_id,
                    WorkspaceUsageMonth.period_started_at == period_started_at,
                )
                .with_for_update()
            )
        ).one_or_none()
        if usage_month is None:
            usage_month = WorkspaceUsageMonth(
                workspace_id=workspace_id,
                period_started_at=period_started_at,
                generated_turns=0,
            )
            self.session.add(usage_month)
        if usage_month.generated_turns >= self.settings.workspace_monthly_generated_turn_limit:
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "WORKSPACE_MONTHLY_QUOTA_EXCEEDED",
                "Cửa hàng đã dùng hết hạn mức tạo phản hồi trong tháng này.",
            )
        usage_month.generated_turns += 1
        usage_month.updated_at = datetime.now(UTC)

    def record_generation(
        self,
        *,
        workspace_id: UUID,
        agent_id: int,
        conversation_id: int | None,
        surface: UsageSurface,
        usage: AgentRuntimeUsage,
    ) -> None:
        self.session.add(
            UsageEvent(
                workspace_id=workspace_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                surface=surface,
                kind="generation",
                status="completed",
                provider="openai" if self.settings.generation_model else None,
                model=self.settings.generation_model,
                model_calls=usage.model_calls,
                tool_calls=usage.tool_calls,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
            )
        )

    def record_vision(
        self,
        *,
        workspace_id: UUID,
        agent_id: int,
        conversation_id: int,
        result: VisionResult,
    ) -> None:
        self.session.add(
            UsageEvent(
                workspace_id=workspace_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                surface="widget",
                kind="vision",
                status="completed",
                provider="openai" if self.settings.vision_model else None,
                model=self.settings.vision_model,
                model_calls=1,
                tool_calls=0,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
            )
        )

    async def summary(self, user: User, workspace_id: UUID) -> UsageSummaryResponse:
        workspace, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền xem mức sử dụng của cửa hàng.",
            )
        return await self.summary_for_workspace(workspace)

    async def summary_for_workspace(self, workspace: Workspace) -> UsageSummaryResponse:
        period_started_at, period_ends_at = month_bounds(workspace.timezone)
        generated_turns = await self.session.scalar(
            select(WorkspaceUsageMonth.generated_turns).where(
                WorkspaceUsageMonth.workspace_id == workspace.id,
                WorkspaceUsageMonth.period_started_at == period_started_at,
            )
        )
        row = (
            await self.session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (UsageEvent.kind == "generation", UsageEvent.model_calls),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (UsageEvent.kind == "vision", UsageEvent.model_calls),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(UsageEvent.tool_calls), 0),
                    func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                    func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                    func.coalesce(func.sum(UsageEvent.total_tokens), 0),
                ).where(
                    UsageEvent.workspace_id == workspace.id,
                    UsageEvent.occurred_at >= period_started_at,
                    UsageEvent.occurred_at < period_ends_at,
                )
            )
        ).one()
        used = int(generated_turns or 0)
        limit = self.settings.workspace_monthly_generated_turn_limit
        return UsageSummaryResponse(
            period_started_at=period_started_at,
            period_ends_at=period_ends_at,
            timezone=workspace.timezone,
            generated_turns=used,
            generated_turn_limit=limit,
            generated_turns_remaining=max(limit - used, 0),
            generation_model_calls=int(row[0]),
            vision_model_calls=int(row[1]),
            tool_calls=int(row[2]),
            input_tokens=int(row[3]),
            output_tokens=int(row[4]),
            total_tokens=int(row[5]),
        )
