import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.channels.contracts import CredentialVault
from agent_hub_api.channels.service import ChannelService, ChannelStateError
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.facebook.contracts import FacebookGraphGateway
from agent_hub_api.facebook.schemas import (
    FacebookConnectionCreateRequest,
    FacebookConnectionListResponse,
    FacebookConnectionResponse,
)
from agent_hub_api.facebook.service import FacebookConnectionService
from agent_hub_api.facebook.webhook import FacebookWebhookAdapter, FacebookWebhookError
from agent_hub_api.identity.dependencies import get_current_user, get_request_settings, require_csrf
from agent_hub_api.identity.models import User

admin_router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/channels/facebook",
    tags=["facebook"],
)
webhook_router = APIRouter(prefix="/api/v1/webhooks/facebook", tags=["facebook-webhook"])


def _vault(request: Request) -> CredentialVault:
    value = getattr(request.app.state, "credential_vault", None)
    if value is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CREDENTIAL_VAULT_UNAVAILABLE",
            "Kho thông tin xác thực chưa được cấu hình.",
        )
    return cast(CredentialVault, value)


def _graph(request: Request) -> FacebookGraphGateway:
    value = getattr(request.app.state, "facebook_graph_gateway", None)
    if value is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "FACEBOOK_NOT_CONFIGURED",
            "Facebook chưa được cấu hình.",
        )
    return cast(FacebookGraphGateway, value)


def _service(request: Request, session: AsyncSession) -> FacebookConnectionService:
    return FacebookConnectionService(session, vault=_vault(request), graph=_graph(request))


@admin_router.get("", response_model=FacebookConnectionListResponse)
async def list_connections(
    workspace_id: UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FacebookConnectionListResponse:
    return await _service(request, session).list(user, workspace_id)


@admin_router.post(
    "",
    response_model=FacebookConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_connection(
    workspace_id: UUID,
    payload: FacebookConnectionCreateRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FacebookConnectionResponse:
    return await _service(request, session).create(user, workspace_id, payload)


@admin_router.post(
    "/{connection_id}/health",
    response_model=FacebookConnectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def verify_connection_health(
    workspace_id: UUID,
    connection_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FacebookConnectionResponse:
    return await _service(request, session).verify_health(user, workspace_id, connection_id)


@admin_router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def revoke_connection(
    workspace_id: UUID,
    connection_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    await _service(request, session).revoke(user, workspace_id, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@webhook_router.get("")
async def verify_webhook(request: Request) -> Response:
    settings = get_request_settings(request)
    verify_token = settings.facebook_webhook_verify_token
    if verify_token is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "FACEBOOK_NOT_CONFIGURED",
            "Facebook chưa được cấu hình.",
        )
    mode = request.query_params.get("hub.mode", "")
    supplied = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    if (
        mode != "subscribe"
        or len(supplied) != len(verify_token)
        or not hmac.compare_digest(supplied, verify_token)
        or not challenge
        or len(challenge) > 500
    ):
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "FACEBOOK_CHALLENGE_INVALID",
            "Webhook challenge không hợp lệ.",
        )
    return Response(content=challenge, media_type="text/plain")


@webhook_router.post("")
async def receive_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    settings = get_request_settings(request)
    if settings.facebook_app_secret is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "FACEBOOK_NOT_CONFIGURED",
            "Facebook chưa được cấu hình.",
        )
    raw_body = await _bounded_raw_body(request, settings.facebook_webhook_max_bytes)
    try:
        events = FacebookWebhookAdapter(settings.facebook_app_secret).verify_and_normalize(
            raw_body=raw_body,
            headers=request.headers,
        )
    except FacebookWebhookError as exc:
        http_status = (
            status.HTTP_401_UNAUTHORIZED
            if exc.code == "FACEBOOK_SIGNATURE_INVALID"
            else status.HTTP_400_BAD_REQUEST
        )
        raise ApiError(http_status, exc.code, "Facebook webhook không hợp lệ.") from exc

    retention_until = datetime.now(UTC) + timedelta(
        days=settings.facebook_message_retention_days
    )
    channel_service = ChannelService(session)
    for event in events:
        try:
            await channel_service.ingest_verified(event, retention_until=retention_until)
        except ChannelStateError as exc:
            if exc.code not in {"CONNECTION_NOT_FOUND", "CONNECTION_NOT_READY"}:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "FACEBOOK_EVENT_CONFLICT",
                    "Facebook webhook không thể được xử lý.",
                ) from exc
    return Response(content="EVENT_RECEIVED", media_type="text/plain")


async def _bounded_raw_body(request: Request, maximum_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
            if declared_length < 0:
                raise ValueError
            if declared_length > maximum_bytes:
                raise ApiError(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "FACEBOOK_WEBHOOK_TOO_LARGE",
                    "Facebook webhook vượt quá giới hạn.",
                )
        except ValueError as exc:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "FACEBOOK_CONTENT_LENGTH_INVALID",
                "Content-Length không hợp lệ.",
            ) from exc
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum_bytes:
            raise ApiError(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "FACEBOOK_WEBHOOK_TOO_LARGE",
                "Facebook webhook vượt quá giới hạn.",
            )
    return bytes(body)
