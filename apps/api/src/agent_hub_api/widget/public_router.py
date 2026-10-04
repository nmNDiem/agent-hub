from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    AgentRuntimeError,
    GroundedAgentResponse,
)
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.widget.execution import resolve_revision_execution_context
from agent_hub_api.widget.public_mapper import to_public_grounded_response
from agent_hub_api.widget.public_schemas import (
    PublicGroundedResponse,
    WidgetConversationResponse,
    WidgetMessageRequest,
    WidgetSessionResponse,
    WidgetTranscriptResponse,
)
from agent_hub_api.widget.visitor_service import PreparedTurn, WidgetVisitorService

router = APIRouter(prefix="/api/v1/widget", tags=["widget-public"])
logger = logging.getLogger(__name__)


class PublishedRuntimeRunner(Protocol):
    async def run_with_context(
        self,
        context: AgentExecutionContext,
        *,
        question: str,
        history: tuple[AgentConversationTurn, ...] = (),
    ) -> GroundedAgentResponse: ...


PublishedRuntimeFactory = Callable[[AsyncSession], PublishedRuntimeRunner]


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_runtime_factory(request: Request) -> PublishedRuntimeFactory:
    factory = cast(
        PublishedRuntimeFactory | None,
        getattr(request.app.state, "agent_runtime_factory", None),
    )
    if factory is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AGENT_RUNTIME_DISABLED",
            "Chatbot hiện chưa sẵn sàng.",
        )
    return factory


def _service(session: AsyncSession, settings: Settings) -> WidgetVisitorService:
    return WidgetVisitorService(session, settings)


def _required_origin(origin: str | None) -> str:
    if origin is None:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "ORIGIN_REQUIRED",
            "Yêu cầu phải có Origin hợp lệ.",
        )
    return origin


def _bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_WIDGET_SESSION",
            "Phiên chat không hợp lệ.",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token or len(token) > 256:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_WIDGET_SESSION",
            "Phiên chat không hợp lệ.",
        )
    return token


def _request_key(value: str | None) -> str:
    key = value.strip() if value is not None else ""
    if not 8 <= len(key) <= 128 or any(ord(character) < 33 for character in key):
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key phải có từ 8 đến 128 ký tự hiển thị.",
        )
    return key


def _event(name: str, payload: object) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n"


def _text_chunks(value: str, size: int = 96) -> list[str]:
    return [value[index : index + size] for index in range(0, len(value), size)]


def _fallback_response(message: str) -> PublicGroundedResponse:
    return PublicGroundedResponse(
        text=message,
        product_cards=[],
        sources=[],
        usage={
            "model_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
    )


async def _emit_response(
    turn: PreparedTurn, response: PublicGroundedResponse
) -> AsyncIterator[str]:
    yield _event("message.start", {"message_id": str(turn.response_id)})
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
        {"message_id": str(turn.response_id), "usage": response.usage},
    )


async def _event_stream(
    request: Request,
    session: AsyncSession,
    service: WidgetVisitorService,
    runner: PublishedRuntimeRunner,
    turn: PreparedTurn,
    *,
    token: str,
    origin: str,
) -> AsyncIterator[str]:
    if turn.replay is not None:
        async for event in _emit_response(turn, turn.replay):
            yield event
        return

    yield _event("message.start", {"message_id": str(turn.response_id)})
    context = await resolve_revision_execution_context(session, turn.context.revision)
    await session.rollback()
    task = asyncio.create_task(
        runner.run_with_context(
            context,
            question=turn.question,
            history=turn.history,
        )
    )
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=10)
            if await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await session.rollback()
                await service.cancel_turn(turn, code="CLIENT_DISCONNECTED")
                return
            if not task.done():
                yield _event("heartbeat", {})
        response = to_public_grounded_response(
            await task,
            allowed_origin=turn.context.origin,
        )
        await session.rollback()
        await service.complete_turn(
            turn,
            token=token,
            origin=origin,
            response=response,
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
            {"message_id": str(turn.response_id), "usage": response.usage},
        )
    except AgentRuntimeError as exc:
        logger.warning(
            "Widget runtime fallback code=%s conversation_id=%s request_id=%s",
            exc.code,
            turn.conversation_public_id,
            getattr(request.state, "request_id", "unknown"),
        )
        response = _fallback_response(exc.public_message)
        await session.rollback()
        await service.complete_turn(turn, token=token, origin=origin, response=response)
        for chunk in _text_chunks(response.text):
            yield _event("message.delta", {"text": chunk})
        yield _event(
            "message.completed",
            {"message_id": str(turn.response_id), "usage": response.usage},
        )
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await session.rollback()
        await service.cancel_turn(turn, code="STREAM_CANCELLED")
        raise
    except Exception:
        logger.exception(
            "Widget stream failed conversation_id=%s request_id=%s",
            turn.conversation_public_id,
            getattr(request.state, "request_id", "unknown"),
        )
        response = _fallback_response(
            "Mình chưa thể kiểm tra thông tin ngay lúc này. Bạn thử lại sau một chút nhé."
        )
        try:
            await session.rollback()
            await service.complete_turn(turn, token=token, origin=origin, response=response)
        except Exception:
            logger.exception(
                "Widget fallback persistence failed conversation_id=%s",
                turn.conversation_public_id,
            )
            await service.cancel_turn(turn, code="GENERATION_FAILED")
        for chunk in _text_chunks(response.text):
            yield _event("message.delta", {"text": chunk})
        yield _event(
            "message.completed",
            {"message_id": str(turn.response_id), "usage": response.usage},
        )


@router.options("/{path:path}", include_in_schema=False)
async def widget_preflight(path: str) -> Response:
    del path
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": "Authorization,Content-Type,Idempotency-Key",
            "Access-Control-Max-Age": "600",
        },
    )


@router.post("/{public_agent_id}/sessions", response_model=WidgetSessionResponse)
async def create_widget_session(
    public_agent_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
) -> WidgetSessionResponse:
    client_address = request.client.host if request.client is not None else "unknown"
    return await _service(session, settings).create_session(
        public_agent_id=public_agent_id,
        origin=_required_origin(origin),
        client_address=client_address,
    )


@router.post("/conversations", response_model=WidgetConversationResponse, status_code=201)
async def create_widget_conversation(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> WidgetConversationResponse:
    return await _service(session, settings).create_conversation(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
    )


@router.get(
    "/conversations/{conversation_public_id}/messages",
    response_model=WidgetTranscriptResponse,
)
async def get_widget_transcript(
    conversation_public_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> WidgetTranscriptResponse:
    return await _service(session, settings).transcript(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        public_id=conversation_public_id,
    )


@router.post("/conversations/{conversation_public_id}/messages")
async def stream_widget_message(
    conversation_public_id: UUID,
    payload: WidgetMessageRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    runtime_factory: Annotated[PublishedRuntimeFactory, Depends(get_runtime_factory)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    resolved_origin = _required_origin(origin)
    token = _bearer_token(authorization)
    service = _service(session, settings)
    turn = await service.prepare_turn(
        token=token,
        origin=resolved_origin,
        conversation_public_id=conversation_public_id,
        request_key=_request_key(idempotency_key),
        question=payload.message,
    )
    return StreamingResponse(
        _event_stream(
            request,
            session,
            service,
            runtime_factory(session),
            turn,
            token=token,
            origin=resolved_origin,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_public_id}/stream")
async def replay_widget_message(
    conversation_public_id: UUID,
    request_key: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    turn = await _service(session, settings).replay_turn(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        conversation_public_id=conversation_public_id,
        request_key=_request_key(request_key),
    )
    assert turn.replay is not None
    return StreamingResponse(
        _emit_response(turn, turn.replay),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.delete(
    "/conversations/{conversation_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_widget_conversation(
    conversation_public_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    await _service(session, settings).delete_conversation(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        conversation_public_id=conversation_public_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
