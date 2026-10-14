import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.channels.contracts import CredentialVault
from agent_hub_api.channels.models import ChannelConnection, ChannelOAuthAttempt
from agent_hub_api.channels.service import ChannelService, ChannelStateError
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.dependencies import get_current_user, get_request_settings, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.models import Workspace
from agent_hub_api.zalo.contracts import ZaloGateway
from agent_hub_api.zalo.credentials import ZaloCredentialError, decode_bundle
from agent_hub_api.zalo.schemas import (
    ZaloConnectionListResponse,
    ZaloConnectionResponse,
    ZaloOAuthStartRequest,
    ZaloOAuthStartResponse,
    ZaloWebhookSecretRequest,
)
from agent_hub_api.zalo.service import ZaloConnectionService
from agent_hub_api.zalo.tokens import ZaloTokenManager
from agent_hub_api.zalo.webhook import ZaloWebhookAdapter, ZaloWebhookError, extract_oa_id

admin_router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/channels/zalo", tags=["zalo"])
oauth_router = APIRouter(prefix="/api/v1/channels/zalo/oauth", tags=["zalo-oauth"])
webhook_router = APIRouter(prefix="/api/v1/webhooks/zalo", tags=["zalo-webhook"])


def _vault(request: Request) -> CredentialVault:
    value = getattr(request.app.state, "credential_vault", None)
    if value is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CREDENTIAL_VAULT_UNAVAILABLE",
            "Kho thông tin xác thực chưa được cấu hình.",
        )
    return cast(CredentialVault, value)


def _gateway(request: Request) -> ZaloGateway:
    value = getattr(request.app.state, "zalo_gateway", None)
    if value is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ZALO_NOT_CONFIGURED",
            "Zalo chưa được cấu hình.",
        )
    return cast(ZaloGateway, value)


def _tokens(request: Request) -> ZaloTokenManager:
    value = getattr(request.app.state, "zalo_token_manager", None)
    if value is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ZALO_NOT_CONFIGURED",
            "Zalo chưa được cấu hình.",
        )
    return cast(ZaloTokenManager, value)


def _service(request: Request, session: AsyncSession) -> ZaloConnectionService:
    settings = get_request_settings(request)
    if settings.zalo_app_id is None or settings.zalo_oauth_redirect_uri is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ZALO_NOT_CONFIGURED",
            "Zalo chưa được cấu hình.",
        )
    return ZaloConnectionService(
        session,
        vault=_vault(request),
        gateway=_gateway(request),
        tokens=_tokens(request),
        app_id=settings.zalo_app_id,
        redirect_uri=settings.zalo_oauth_redirect_uri,
        oauth_attempt_minutes=settings.zalo_oauth_attempt_minutes,
    )


@admin_router.get("", response_model=ZaloConnectionListResponse)
async def list_connections(
    workspace_id: UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ZaloConnectionListResponse:
    return await _service(request, session).list(user, workspace_id)


@admin_router.post(
    "/oauth/start",
    response_model=ZaloOAuthStartResponse,
    dependencies=[Depends(require_csrf)],
)
async def start_oauth(
    workspace_id: UUID,
    payload: ZaloOAuthStartRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ZaloOAuthStartResponse:
    return await _service(request, session).start_oauth(user, workspace_id, payload)


@admin_router.put(
    "/{connection_id}/webhook-secret",
    response_model=ZaloConnectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def set_webhook_secret(
    workspace_id: UUID,
    connection_id: int,
    payload: ZaloWebhookSecretRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ZaloConnectionResponse:
    return await _service(request, session).set_webhook_secret(
        user, workspace_id, connection_id, payload.webhook_secret.get_secret_value()
    )


@admin_router.post(
    "/{connection_id}/health",
    response_model=ZaloConnectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def verify_health(
    workspace_id: UUID,
    connection_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ZaloConnectionResponse:
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


@oauth_router.get("/callback")
async def oauth_callback(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    state_value: Annotated[str, Query(alias="state", min_length=1, max_length=256)],
    code: Annotated[str | None, Query(max_length=4096)] = None,
    oa_id: Annotated[str | None, Query(max_length=255)] = None,
    error: Annotated[str | None, Query(max_length=255)] = None,
) -> RedirectResponse:
    base = get_request_settings(request).allowed_origins[0].rstrip("/")
    state_hash = hashlib.sha256(state_value.encode()).hexdigest()
    async with session.begin():
        candidate = (
            await session.execute(
                select(ChannelOAuthAttempt.workspace_id, ChannelOAuthAttempt.agent_id).where(
                    ChannelOAuthAttempt.state_hash == state_hash,
                    ChannelOAuthAttempt.user_id == user.id,
                )
            )
        ).one_or_none()
        candidate_workspace_id = candidate.workspace_id if candidate is not None else None
        candidate_agent_id = candidate.agent_id if candidate is not None else None
    try:
        workspace_id = await _service(request, session).complete_oauth(
            user,
            state=state_value,
            code=code,
            oa_id=oa_id,
            provider_error=error,
        )
    except ApiError as exc:
        workspace_slug = (
            await session.scalar(
                select(Workspace.slug).where(Workspace.id == candidate_workspace_id)
            )
            if candidate_workspace_id is not None
            else None
        )
        agent_public_id = (
            await session.scalar(
                select(Agent.public_id).where(
                    Agent.workspace_id == candidate_workspace_id,
                    Agent.id == candidate_agent_id,
                )
            )
            if candidate_workspace_id is not None and candidate_agent_id is not None
            else None
        )
        agent_query = f"agent={quote(str(agent_public_id))}&" if agent_public_id is not None else ""
        error_path = (
            f"/app/{quote(workspace_slug)}/chatbots?{agent_query}channel=zalo&oauth=error&code={quote(exc.code)}"
            if workspace_slug is not None
            else f"/app?channel=zalo&oauth=error&code={quote(exc.code)}"
        )
        return RedirectResponse(
            f"{base}{error_path}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    workspace_slug = await session.scalar(
        select(Workspace.slug).where(Workspace.id == workspace_id)
    )
    agent_public_id = (
        await session.scalar(
            select(Agent.public_id).where(
                Agent.workspace_id == workspace_id,
                Agent.id == candidate_agent_id,
            )
        )
        if candidate_agent_id is not None
        else None
    )
    agent_query = f"agent={quote(str(agent_public_id))}&" if agent_public_id is not None else ""
    success_path = (
        f"/app/{quote(workspace_slug)}/chatbots?{agent_query}channel=zalo&oauth=success"
        if workspace_slug is not None
        else "/app?channel=zalo&oauth=success"
    )
    return RedirectResponse(
        f"{base}{success_path}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@webhook_router.post("")
async def receive_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    settings = get_request_settings(request)
    if settings.zalo_app_id is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE, "ZALO_NOT_CONFIGURED", "Zalo chưa được cấu hình."
        )
    raw_body = await _bounded_raw_body(request, settings.zalo_webhook_max_bytes)
    try:
        oa_id = extract_oa_id(raw_body, app_id=settings.zalo_app_id)
        async with session.begin():
            connection = (
                await session.scalars(
                    select(ChannelConnection).where(
                        ChannelConnection.provider == "zalo",
                        ChannelConnection.external_account_id == oa_id,
                        ChannelConnection.lifecycle_state == "active",
                    )
                )
            ).one_or_none()
        if connection is None or connection.credential_ref is None:
            raise ZaloWebhookError("ZALO_CONNECTION_NOT_FOUND")
        bundle = decode_bundle(await _vault(request).resolve(connection.credential_ref))
        if bundle.webhook_secret is None:
            raise ZaloWebhookError("ZALO_WEBHOOK_SECRET_MISSING")
        events = ZaloWebhookAdapter(
            app_id=settings.zalo_app_id,
            webhook_secret=bundle.webhook_secret,
        ).verify_and_normalize(raw_body=raw_body, headers=dict(request.headers))
    except (CredentialVaultError, ZaloCredentialError) as exc:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CREDENTIAL_VAULT_UNAVAILABLE",
            "Kho thông tin xác thực tạm thời không khả dụng.",
        ) from exc
    except ZaloWebhookError as exc:
        http_status = (
            status.HTTP_401_UNAUTHORIZED
            if exc.code in {"ZALO_SIGNATURE_INVALID", "ZALO_CONNECTION_NOT_FOUND"}
            else status.HTTP_400_BAD_REQUEST
        )
        raise ApiError(http_status, exc.code, "Zalo webhook không hợp lệ.") from exc
    retention_until = datetime.now(UTC) + timedelta(days=settings.zalo_message_retention_days)
    channel_service = ChannelService(
        session,
        response_window_hours=settings.zalo_response_window_hours,
        response_job_max_attempts=settings.facebook_response_job_max_attempts,
    )
    for event in events:
        try:
            await channel_service.ingest_verified(event, retention_until=retention_until)
        except ChannelStateError as exc:
            if exc.code not in {"CONNECTION_NOT_FOUND", "CONNECTION_NOT_READY"}:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "ZALO_EVENT_CONFLICT",
                    "Zalo webhook không thể được xử lý.",
                ) from exc
    return Response(content="OK", media_type="text/plain")


async def _bounded_raw_body(request: Request, maximum_bytes: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) < 0:
                raise ValueError
            if int(content_length) > maximum_bytes:
                raise ApiError(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "ZALO_WEBHOOK_TOO_LARGE",
                    "Zalo webhook vượt quá giới hạn.",
                )
        except ValueError as exc:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "ZALO_CONTENT_LENGTH_INVALID",
                "Content-Length không hợp lệ.",
            ) from exc
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum_bytes:
            raise ApiError(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "ZALO_WEBHOOK_TOO_LARGE",
                "Zalo webhook vượt quá giới hạn.",
            )
    return bytes(body)
