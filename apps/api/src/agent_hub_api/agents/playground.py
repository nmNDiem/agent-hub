from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Literal, Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentRuntimeError,
    GroundedAgentResponse,
)
from agent_hub_api.agents.service import AgentService
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.telemetry.service import TelemetryService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/agents", tags=["playground"])
logger = logging.getLogger(__name__)


class PlaygroundHistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3_000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("History content cannot be blank")
        return cleaned


class PlaygroundMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    history: list[PlaygroundHistoryTurn] = Field(default_factory=list, max_length=8)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def bound_history(self) -> PlaygroundMessageRequest:
        if sum(len(turn.content) for turn in self.history) > 12_000:
            raise ValueError("History exceeds the maximum character count")
        return self


class AgentRuntimeRunner(Protocol):
    async def run(
        self,
        *,
        workspace_id: UUID,
        public_agent_id: UUID,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse: ...


AgentRuntimeFactory = Callable[[AsyncSession], AgentRuntimeRunner]


def get_runtime_factory(request: Request) -> AgentRuntimeFactory:
    factory = cast(
        AgentRuntimeFactory | None,
        getattr(request.app.state, "agent_runtime_factory", None),
    )
    if factory is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AGENT_RUNTIME_DISABLED",
            "Playground chưa sẵn sàng. Hãy cấu hình OpenAI và Qdrant rồi thử lại.",
        )
    return factory


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _event(name: str, payload: object) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"


def _text_chunks(value: str, size: int = 96) -> list[str]:
    return [value[index : index + size] for index in range(0, len(value), size)]


def _completed_payload(
    message_id: str, response: GroundedAgentResponse | None = None
) -> dict[str, object]:
    usage = response.usage.model_dump(mode="json") if response is not None else {}
    return {"message_id": message_id, "usage": usage}


async def _event_stream(
    request: Request,
    session: AsyncSession,
    settings: Settings,
    runner: AgentRuntimeRunner,
    *,
    workspace_id: UUID,
    public_agent_id: UUID,
    agent_id: int,
    payload: PlaygroundMessageRequest,
) -> AsyncIterator[str]:
    response_id = str(new_uuid_v7())
    yield _event("message.start", {"message_id": response_id})
    task = asyncio.create_task(
        runner.run(
            workspace_id=workspace_id,
            public_agent_id=public_agent_id,
            question=payload.message,
            history=tuple(
                AgentConversationTurn(role=turn.role, content=turn.content)
                for turn in payload.history
            ),
        )
    )
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=10)
            if await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return
            if not task.done():
                yield _event("heartbeat", {})
        response = await task
        await session.rollback()
        async with session.begin():
            TelemetryService(session, settings).record_generation(
                workspace_id=workspace_id,
                agent_id=agent_id,
                conversation_id=None,
                surface="playground",
                usage=response.usage,
            )
        for chunk in _text_chunks(response.text):
            yield _event("message.delta", {"text": chunk})
            await asyncio.sleep(0)
        if response.product_cards:
            yield _event(
                "product.cards",
                {"items": [item.model_dump(mode="json") for item in response.product_cards]},
            )
        if response.sources:
            yield _event(
                "source.refs",
                {"items": [item.model_dump(mode="json") for item in response.sources]},
            )
        yield _event(
            "message.completed",
            _completed_payload(response_id, response),
        )
    except AgentRuntimeError as exc:
        logger.warning(
            "Playground runtime fallback code=%s workspace_id=%s public_agent_id=%s request_id=%s",
            exc.code,
            workspace_id,
            public_agent_id,
            getattr(request.state, "request_id", "unknown"),
        )
        for chunk in _text_chunks(exc.public_message):
            yield _event("message.delta", {"text": chunk})
        yield _event("message.completed", _completed_payload(response_id))
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
    except Exception:
        logger.exception(
            "Playground stream failed workspace_id=%s public_agent_id=%s request_id=%s",
            workspace_id,
            public_agent_id,
            getattr(request.state, "request_id", "unknown"),
        )
        fallback = "Mình chưa thể kiểm tra thông tin ngay lúc này. Bạn thử lại sau một chút nhé."
        for chunk in _text_chunks(fallback):
            yield _event("message.delta", {"text": chunk})
        yield _event("message.completed", _completed_payload(response_id))


@router.post(
    "/{public_agent_id}/playground/messages:stream",
    dependencies=[Depends(require_csrf)],
)
async def stream_playground_message(
    workspace_id: UUID,
    public_agent_id: UUID,
    payload: PlaygroundMessageRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    runtime_factory: Annotated[AgentRuntimeFactory, Depends(get_runtime_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    # Complete authorization before response headers are committed.
    await AgentService(session).get(user, workspace_id, public_agent_id)
    telemetry = TelemetryService(session, settings)
    agent_id = await telemetry.resolve_agent_id(workspace_id, public_agent_id)
    await session.rollback()
    async with session.begin():
        await telemetry.reserve_generation_turn(workspace_id, agent_id)
    runner = runtime_factory(session)
    return StreamingResponse(
        _event_stream(
            request,
            session,
            settings,
            runner,
            workspace_id=workspace_id,
            public_agent_id=public_agent_id,
            agent_id=agent_id,
            payload=payload,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
