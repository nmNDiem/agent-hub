from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, Protocol, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Request, Response, UploadFile, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.runtime import (
    AgentConversationTurn,
    AgentExecutionContext,
    AgentRuntimeError,
    GroundedAgentResponse,
)
from agent_hub_api.catalog.models import ProductImage
from agent_hub_api.catalog.storage import CatalogStorage, StorageError
from agent_hub_api.contacts.follow_up import FollowUpActionContext
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.leads.schemas import LeadCaptureRequest, LeadCaptureResponse
from agent_hub_api.leads.service import LeadService
from agent_hub_api.widget.execution import resolve_revision_execution_context
from agent_hub_api.widget.image_service import VisitorImageService
from agent_hub_api.widget.image_storage import (
    VisitorImageStorage,
    VisitorImageStorageError,
)
from agent_hub_api.widget.models import WidgetCatalogImageGrant
from agent_hub_api.widget.public_mapper import to_public_grounded_response
from agent_hub_api.widget.public_schemas import (
    PublicGroundedResponse,
    WidgetConversationResponse,
    WidgetImageUploadResponse,
    WidgetMessageRequest,
    WidgetSessionResponse,
    WidgetTranscriptResponse,
)
from agent_hub_api.widget.vision import (
    VisionError,
    VisionGateway,
    VisionPermanentError,
    VisionResult,
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


def get_image_storage(request: Request) -> VisitorImageStorage:
    storage = cast(
        VisitorImageStorage | None,
        getattr(request.app.state, "widget_image_storage", None),
    )
    if storage is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "IMAGE_INPUT_DISABLED",
            "Chatbot hiện chưa hỗ trợ nhận ảnh.",
        )
    return storage


def get_vision_gateway(request: Request) -> VisionGateway:
    gateway = cast(
        VisionGateway | None,
        getattr(request.app.state, "vision_gateway", None),
    )
    if gateway is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "IMAGE_INPUT_DISABLED",
            "Chatbot hiện chưa hỗ trợ nhận ảnh.",
        )
    return gateway


def get_public_catalog_storage(request: Request) -> CatalogStorage:
    storage = cast(
        CatalogStorage | None,
        getattr(request.app.state, "catalog_storage", None),
    )
    if storage is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CATALOG_IMAGE_UNAVAILABLE",
            "Ảnh sản phẩm hiện chưa khả dụng.",
        )
    return storage


def _image_enabled(request: Request) -> bool:
    return bool(getattr(request.app.state, "widget_image_enabled", False))


def _service(
    session: AsyncSession, settings: Settings, *, image_input_enabled: bool = False
) -> WidgetVisitorService:
    return WidgetVisitorService(
        session,
        settings,
        image_input_enabled=image_input_enabled,
    )


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


def _include_vision_usage(
    response: PublicGroundedResponse, result: VisionResult | None
) -> PublicGroundedResponse:
    if result is None:
        return response
    usage = dict(response.usage)
    usage["model_calls"] = usage.get("model_calls", 0) + 1
    usage["input_tokens"] = usage.get("input_tokens", 0) + result.input_tokens
    usage["output_tokens"] = usage.get("output_tokens", 0) + result.output_tokens
    usage["total_tokens"] = usage.get("total_tokens", 0) + result.total_tokens
    return response.model_copy(update={"usage": usage})


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
    image_storage: VisitorImageStorage | None,
    vision_gateway: VisionGateway | None,
    *,
    token: str,
    origin: str,
) -> AsyncIterator[str]:
    if turn.waiting_human:
        yield _event("handoff.waiting", {})
        return
    if turn.replay is not None:
        async for event in _emit_response(turn, turn.replay):
            yield event
        return

    yield _event("message.start", {"message_id": str(turn.response_id)})
    task: asyncio.Task[GroundedAgentResponse] | None = None
    try:
        context = await resolve_revision_execution_context(session, turn.context.revision)
        context = replace(
            context,
            follow_up_action_context=FollowUpActionContext(
                workspace_id=turn.context.workspace_id,
                agent_id=turn.context.agent_id,
                revision_id=turn.context.revision_id,
                conversation_id=turn.conversation_id,
                source_message_id=turn.inbound_message_id,
                channel_connection_id=turn.context.channel_id,
                channel="web",
            ),
        )
        await session.rollback()
        question = turn.question
        vision_result: VisionResult | None = None
        if turn.attachment is not None:
            if image_storage is None or vision_gateway is None:
                raise VisionPermanentError("Image input became unavailable")
            content = await image_storage.download(
                object_key=turn.attachment.object_key,
                max_bytes=service.settings.widget_image_max_bytes,
            )
            vision_result = await vision_gateway.analyze(
                content=content,
                content_type=turn.attachment.content_type,
            )
            await service.record_attachment_analysis(
                turn,
                analysis=vision_result.observation.model_dump(mode="json"),
            )
            question = f"{turn.question}\n\n{vision_result.observation.prompt_context()}"
        task = asyncio.create_task(
            runner.run_with_context(
                context,
                question=question,
                history=turn.history,
            )
        )
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
        runtime_response = await task
        await session.rollback()
        response = _include_vision_usage(
            await to_public_grounded_response(
                runtime_response,
                allowed_origin=turn.context.origin,
                session=session,
                workspace_id=turn.context.workspace_id,
                widget_session_id=turn.context.session_id,
                grant_expires_at=turn.context.expires_at,
                include_managed_images=getattr(request.app.state, "catalog_storage", None)
                is not None,
            ),
            vision_result,
        )
        completed = await service.complete_turn(
            turn,
            token=token,
            origin=origin,
            response=response,
            product_ids=tuple(card.product_id for card in runtime_response.product_cards),
            generation_usage=runtime_response.usage,
            vision_result=vision_result,
        )
        if not completed:
            yield _event("handoff.waiting", {})
            return
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
        if not await service.complete_turn(turn, token=token, origin=origin, response=response):
            yield _event("handoff.waiting", {})
            return
        for chunk in _text_chunks(response.text):
            yield _event("message.delta", {"text": chunk})
        yield _event(
            "message.completed",
            {"message_id": str(turn.response_id), "usage": response.usage},
        )
    except (VisionError, VisitorImageStorageError) as exc:
        logger.warning(
            "Widget image fallback error=%s conversation_id=%s request_id=%s",
            type(exc).__name__,
            turn.conversation_public_id,
            getattr(request.state, "request_id", "unknown"),
        )
        response = _fallback_response(
            "Mình chưa thể phân tích ảnh này lúc này. "
            "Bạn có thể mô tả sản phẩm để mình tìm giúp nhé."
        )
        await session.rollback()
        if not await service.complete_turn(turn, token=token, origin=origin, response=response):
            yield _event("handoff.waiting", {})
            return
        for chunk in _text_chunks(response.text):
            yield _event("message.delta", {"text": chunk})
        yield _event(
            "message.completed",
            {"message_id": str(turn.response_id), "usage": response.usage},
        )
    except asyncio.CancelledError:
        if task is not None:
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
            completed = await service.complete_turn(
                turn, token=token, origin=origin, response=response
            )
            if not completed:
                yield _event("handoff.waiting", {})
                return
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
    return await _service(
        session, settings, image_input_enabled=_image_enabled(request)
    ).create_session(
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


@router.post(
    "/conversations/{conversation_public_id}/leads",
    response_model=LeadCaptureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def capture_widget_lead(
    conversation_public_id: UUID,
    payload: LeadCaptureRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> LeadCaptureResponse:
    return await LeadService(session, settings).capture(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        conversation_public_id=conversation_public_id,
        idempotency_key=_request_key(idempotency_key),
        payload=payload,
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
    image_enabled = _image_enabled(request)
    service = _service(session, settings, image_input_enabled=image_enabled)
    turn = await service.prepare_turn(
        token=token,
        origin=resolved_origin,
        conversation_public_id=conversation_public_id,
        request_key=_request_key(idempotency_key),
        question=payload.message,
        attachment_id=payload.attachment_id,
    )
    return StreamingResponse(
        _event_stream(
            request,
            session,
            service,
            runtime_factory(session),
            turn,
            cast(
                VisitorImageStorage | None,
                getattr(request.app.state, "widget_image_storage", None),
            ),
            cast(
                VisionGateway | None,
                getattr(request.app.state, "vision_gateway", None),
            ),
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


@router.post(
    "/uploads/images",
    response_model=WidgetImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_widget_image(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[VisitorImageStorage, Depends(get_image_storage)],
    vision_gateway: Annotated[VisionGateway, Depends(get_vision_gateway)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> WidgetImageUploadResponse:
    del vision_gateway
    content = await file.read(settings.widget_image_max_bytes + 1)
    return await VisitorImageService(session, settings, storage).upload(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        content=content,
        declared_content_type=file.content_type or "application/octet-stream",
    )


@router.delete("/uploads/images/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget_image(
    attachment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[VisitorImageStorage, Depends(get_image_storage)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    await VisitorImageService(session, settings, storage).delete(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
        attachment_id=attachment_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/product-images/{grant_public_id}")
async def get_widget_product_image(
    grant_public_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[CatalogStorage, Depends(get_public_catalog_storage)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> RedirectResponse:
    context = await _service(session, settings).resolve_context(
        token=_bearer_token(authorization),
        origin=_required_origin(origin),
    )
    row = (
        await session.execute(
            select(WidgetCatalogImageGrant, ProductImage)
            .join(
                ProductImage,
                (ProductImage.workspace_id == WidgetCatalogImageGrant.workspace_id)
                & (ProductImage.id == WidgetCatalogImageGrant.product_image_id),
            )
            .where(
                WidgetCatalogImageGrant.workspace_id == context.workspace_id,
                WidgetCatalogImageGrant.session_id == context.session_id,
                WidgetCatalogImageGrant.public_id == grant_public_id,
                WidgetCatalogImageGrant.expires_at > datetime.now(UTC),
                ProductImage.status == "active",
                ProductImage.object_key.is_not(None),
            )
        )
    ).one_or_none()
    if row is None or row[1].object_key is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "NOT_FOUND",
            "Không tìm thấy ảnh sản phẩm.",
        )
    try:
        signed_url = await storage.create_signed_url(
            object_key=row[1].object_key,
            expires_in=settings.storage_signed_url_seconds,
        )
    except StorageError as exc:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CATALOG_IMAGE_UNAVAILABLE",
            "Ảnh sản phẩm hiện chưa khả dụng.",
        ) from exc
    return RedirectResponse(
        signed_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Cache-Control": "private, no-store"},
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
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    origin: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    token = _bearer_token(authorization)
    resolved_origin = _required_origin(origin)
    service = _service(session, settings)
    pending_cleanup = await service.delete_conversation(
        token=token,
        origin=resolved_origin,
        conversation_public_id=conversation_public_id,
    )
    storage = cast(
        VisitorImageStorage | None,
        getattr(request.app.state, "widget_image_storage", None),
    )
    for pending in pending_cleanup:
        if storage is None:
            await service.finish_image_cleanup(pending, error_code="storage_unconfigured")
            continue
        try:
            await storage.delete(object_key=pending.object_key)
        except VisitorImageStorageError:
            await service.finish_image_cleanup(pending, error_code="storage_delete_failed")
            logger.warning(
                "widget_image_cleanup_deferred image_id=%s request_id=%s",
                pending.image_id,
                getattr(request.state, "request_id", "unknown"),
            )
        else:
            await service.finish_image_cleanup(pending)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
