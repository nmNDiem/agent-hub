import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.agents.repository import AgentRepository
from agent_hub_api.agents.schemas import (
    AgentCatalogScopeRequest,
    AgentCatalogScopeResponse,
    AgentCreateRequest,
    AgentIcon,
    AgentListResponse,
    AgentResponse,
    AgentStatus,
    AgentUpdateRequest,
    IntakeChoiceOption,
    IntakeDefinition,
    IntakeFieldDefinition,
)
from agent_hub_api.catalog.models import CatalogCollection, Location
from agent_hub_api.catalog.read_models import AuthorizedCatalogScope
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService

_DEFAULT_AGENT_COPY: dict[str, tuple[str, str]] = {
    "vi": (
        "Xin chào! Mình có thể giúp bạn tìm hiểu thông tin. Bạn đang quan tâm điều gì?",
        "Trò chuyện thân thiện, tự nhiên và chủ động. "
        "Trả lời rõ ràng, vừa đủ; ưu tiên nhu cầu của người dùng và đặt một câu hỏi tiếp theo "
        "khi điều đó giúp hỗ trợ tốt hơn. Chỉ sử dụng thông tin được cung cấp và nói rõ "
        "khi chưa thể xác minh.",
    ),
    "en": (
        "Hello! I can help you find and understand information. What would you like to know?",
        "Be a friendly, natural, and proactive assistant. Give clear, concise answers, "
        "focus on the user's needs, and ask a helpful follow-up question when appropriate. "
        "Use only the information provided and be transparent when something cannot be verified.",
    ),
}


def _default_agent_copy(locale: str) -> tuple[str, str]:
    language = locale.casefold().split("-", maxsplit=1)[0]
    return _DEFAULT_AGENT_COPY.get(language, _DEFAULT_AGENT_COPY["en"])


def _stored_intake(value: dict[str, object] | None) -> IntakeDefinition | None:
    return IntakeDefinition.model_validate(value) if value is not None else None


def _materialize_intake(
    definition: IntakeDefinition,
    current: IntakeDefinition | None,
) -> IntakeDefinition:
    current_fields = (
        {field.key: field for field in current.fields if field.key is not None}
        if current is not None
        else {}
    )
    fields: list[IntakeFieldDefinition] = []
    for field in definition.fields:
        if field.key is not None and field.key not in current_fields:
            raise ValueError("Intake field keys are server-generated")
        field_key = field.key or new_uuid_v7()
        current_field = current_fields.get(field_key)
        current_options = {
            option.key: option
            for option in (current_field.options if current_field is not None else [])
            if option.key is not None
        }
        options: list[IntakeChoiceOption] = []
        for option in field.options:
            if option.key is not None and option.key not in current_options:
                raise ValueError("Intake option keys are server-generated")
            options.append(option.model_copy(update={"key": option.key or new_uuid_v7()}))
        fields.append(field.model_copy(update={"key": field_key, "options": options}))
    disclosure_canonical = json.dumps(
        {"purpose": definition.purpose, "disclosure": definition.disclosure},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    disclosure_version = (
        "intake-v1-" + hashlib.sha256(disclosure_canonical.encode()).hexdigest()[:16]
    )
    return IntakeDefinition(
        purpose=definition.purpose,
        disclosure=definition.disclosure,
        disclosure_version=disclosure_version,
        fields=fields,
    )


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AgentRepository(session)

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền thay đổi agent.",
            )

    async def _agent(self, workspace_id: UUID, public_id: UUID) -> Agent:
        agent = await self.repository.get_active(workspace_id, public_id)
        if agent is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy agent.",
            )
        return agent

    @staticmethod
    def _response(
        agent: Agent,
        location_ids: list[int],
        collection_ids: list[int],
    ) -> AgentResponse:
        return AgentResponse(
            public_id=agent.public_id,
            name=agent.name,
            icon=cast(AgentIcon, agent.icon),
            color=agent.color,
            greeting=agent.greeting,
            safe_instructions=agent.safe_instructions,
            default_locale=agent.default_locale,
            status=cast(AgentStatus, agent.status),
            follow_up_action_enabled=agent.follow_up_action_enabled,
            intake_action_enabled=agent.intake_action_enabled,
            intake_definition=_stored_intake(agent.intake_definition_json),
            catalog_scope=AgentCatalogScopeResponse(
                location_ids=None if agent.all_locations else location_ids,
                collection_ids=None if agent.all_collections else collection_ids,
            ),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    async def _response_for(self, agent: Agent) -> AgentResponse:
        locations, collections = await self.repository.assignment_maps(
            agent.workspace_id, [agent.id]
        )
        return self._response(agent, locations[agent.id], collections[agent.id])

    async def list(self, user: User, workspace_id: UUID) -> AgentListResponse:
        await self._authorize(user, workspace_id)
        agents = await self.repository.list_active(workspace_id)
        locations, collections = await self.repository.assignment_maps(
            workspace_id, [agent.id for agent in agents]
        )
        return AgentListResponse(
            items=[
                self._response(agent, locations[agent.id], collections[agent.id])
                for agent in agents
            ]
        )

    async def get(self, user: User, workspace_id: UUID, public_id: UUID) -> AgentResponse:
        await self._authorize(user, workspace_id)
        return await self._response_for(await self._agent(workspace_id, public_id))

    async def create(
        self, user: User, workspace_id: UUID, payload: AgentCreateRequest
    ) -> AgentResponse:
        default_greeting, default_personality = _default_agent_copy(payload.default_locale)
        greeting = payload.greeting if "greeting" in payload.model_fields_set else default_greeting
        safe_instructions = (
            payload.safe_instructions
            if "safe_instructions" in payload.model_fields_set
            else default_personality
        )
        try:
            intake_definition = (
                _materialize_intake(payload.intake_definition, None)
                if payload.intake_definition is not None
                else None
            )
        except ValueError as exc:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "INVALID_INTAKE_DEFINITION",
                "Cấu hình thu thập thông tin không hợp lệ.",
            ) from exc
        try:
            async with self.session.begin():
                await self._authorize(user, workspace_id, write=True)
                agent = Agent(
                    public_id=new_uuid_v7(),
                    workspace_id=workspace_id,
                    name=payload.name,
                    icon=payload.icon,
                    color=payload.color,
                    greeting=greeting,
                    safe_instructions=safe_instructions,
                    default_locale=payload.default_locale,
                    follow_up_action_enabled=payload.follow_up_action_enabled,
                    intake_action_enabled=payload.intake_action_enabled,
                    intake_definition_json=(
                        intake_definition.model_dump(mode="json")
                        if intake_definition is not None
                        else None
                    ),
                    created_by_user_id=user.id,
                )
                self.session.add(agent)
                await self.session.flush()
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "AGENT_CREATE_CONFLICT",
                "Không thể tạo agent.",
            ) from exc
        return await self._response_for(agent)

    async def update(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        payload: AgentUpdateRequest,
    ) -> AgentResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            current_intake = _stored_intake(agent.intake_definition_json)
            next_intake = current_intake
            if "intake_definition" in payload.model_fields_set:
                if payload.intake_definition is None:
                    next_intake = None
                else:
                    try:
                        next_intake = _materialize_intake(payload.intake_definition, current_intake)
                    except ValueError as exc:
                        raise ApiError(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "INVALID_INTAKE_DEFINITION",
                            "Cấu hình thu thập thông tin không hợp lệ.",
                        ) from exc
            next_intake_enabled = (
                payload.intake_action_enabled
                if "intake_action_enabled" in payload.model_fields_set
                else agent.intake_action_enabled
            )
            if next_intake_enabled and next_intake is None:
                raise ApiError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "INTAKE_DEFINITION_REQUIRED",
                    "Hãy cấu hình thông tin cần thu thập trước khi bật.",
                )
            for field in payload.model_fields_set:
                value = getattr(payload, field)
                if field == "intake_definition":
                    agent.intake_definition_json = (
                        next_intake.model_dump(mode="json") if next_intake is not None else None
                    )
                    continue
                if (
                    field
                    in {
                        "name",
                        "default_locale",
                        "icon",
                        "color",
                        "follow_up_action_enabled",
                        "intake_action_enabled",
                    }
                    and value is None
                ):
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "VALIDATION_ERROR",
                        f"{field} cannot be null",
                    )
                setattr(agent, field, value)
            agent.updated_at = datetime.now(UTC)
        return await self._response_for(agent)

    async def archive(self, user: User, workspace_id: UUID, public_id: UUID) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            archived_at = datetime.now(UTC)
            agent.archived_at = archived_at
            agent.updated_at = archived_at

    async def replace_catalog_scope(
        self,
        user: User,
        workspace_id: UUID,
        public_id: UUID,
        payload: AgentCatalogScopeRequest,
    ) -> AgentResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self._agent(workspace_id, public_id)
            await self._validate_scope_ids(
                workspace_id,
                location_ids=payload.location_ids,
                collection_ids=payload.collection_ids,
            )
            await self.repository.replace_assignments(
                agent,
                location_ids=payload.location_ids,
                collection_ids=payload.collection_ids,
            )
            agent.updated_at = datetime.now(UTC)
        return await self._response_for(agent)

    async def _validate_scope_ids(
        self,
        workspace_id: UUID,
        *,
        location_ids: Sequence[int] | None,
        collection_ids: Sequence[int] | None,
    ) -> None:
        if location_ids:
            found = set(
                await self.session.scalars(
                    select(Location.id).where(
                        Location.workspace_id == workspace_id,
                        Location.id.in_(location_ids),
                        Location.is_active.is_(True),
                    )
                )
            )
            if found != set(location_ids):
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy location.",
                )
        if collection_ids:
            found = set(
                await self.session.scalars(
                    select(CatalogCollection.id).where(
                        CatalogCollection.workspace_id == workspace_id,
                        CatalogCollection.id.in_(collection_ids),
                        CatalogCollection.is_active.is_(True),
                    )
                )
            )
            if found != set(collection_ids):
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy collection.",
                )


async def resolve_agent_catalog_scope(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    public_agent_id: UUID,
) -> AuthorizedCatalogScope:
    """Resolve immutable catalog authorization after the caller validates agent context."""

    repository = AgentRepository(session)
    agent = await repository.get_active(workspace_id, public_agent_id)
    if agent is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy agent.")
    location_ids, collection_ids = await repository.active_scope_ids(agent)
    return AuthorizedCatalogScope(
        workspace_id=workspace_id,
        allowed_location_ids=location_ids,
        allowed_collection_ids=collection_ids,
    )
