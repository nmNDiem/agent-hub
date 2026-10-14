import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent, AgentRevision
from agent_hub_api.channels.contracts import CredentialVault
from agent_hub_api.channels.models import (
    ChannelAgentBinding,
    ChannelConnection,
    ChannelOAuthAttempt,
)
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService
from agent_hub_api.zalo.contracts import ZaloCredentialBundle, ZaloGateway, ZaloProviderError
from agent_hub_api.zalo.credentials import ZaloCredentialError, decode_bundle, encode_bundle
from agent_hub_api.zalo.schemas import (
    ZaloConnectionListResponse,
    ZaloConnectionResponse,
    ZaloOAuthStartRequest,
    ZaloOAuthStartResponse,
)
from agent_hub_api.zalo.tokens import ZaloTokenError, ZaloTokenManager

logger = logging.getLogger("agent_hub_api.zalo")

ConnectionState = Literal["active", "revoked"]
HealthState = Literal[
    "unknown",
    "healthy",
    "permission_expired",
    "reauth_required",
    "webhook_subscription_failure",
    "delivery_unknown",
]


class ZaloConnectionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        vault: CredentialVault,
        gateway: ZaloGateway,
        tokens: ZaloTokenManager,
        app_id: str,
        redirect_uri: str,
        oauth_attempt_minutes: int = 10,
    ) -> None:
        self.session = session
        self.vault = vault
        self.gateway = gateway
        self.tokens = tokens
        self.app_id = app_id
        self.redirect_uri = redirect_uri
        self.oauth_attempt_minutes = oauth_attempt_minutes

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền quản lý kênh Zalo.",
            )

    async def start_oauth(
        self, user: User, workspace_id: UUID, payload: ZaloOAuthStartRequest
    ) -> ZaloOAuthStartResponse:
        verifier_ref: str | None = None
        verifier = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=self.oauth_attempt_minutes)
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = (
                await self.session.scalars(
                    select(Agent)
                    .where(
                        Agent.workspace_id == workspace_id,
                        Agent.public_id == payload.agent_public_id,
                        Agent.archived_at.is_(None),
                        Agent.status == "published",
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if agent is None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "ZALO_AGENT_NOT_READY",
                    "Chatbot phải được xuất bản trước khi kết nối Zalo.",
                )
            revision = (
                await self.session.scalars(
                    select(AgentRevision)
                    .where(
                        AgentRevision.workspace_id == workspace_id,
                        AgentRevision.agent_id == agent.id,
                    )
                    .order_by(AgentRevision.published_at.desc(), AgentRevision.id.desc())
                    .limit(1)
                )
            ).one_or_none()
            if revision is None:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "ZALO_AGENT_NOT_READY",
                    "Chatbot chưa có phiên bản đã xuất bản.",
                )
            if payload.reauthorize_connection_id is not None:
                connection = await self._connection(
                    workspace_id, payload.reauthorize_connection_id, active=True
                )
                binding = await self.session.scalar(
                    select(ChannelAgentBinding).where(
                        ChannelAgentBinding.workspace_id == workspace_id,
                        ChannelAgentBinding.connection_id == connection.id,
                        ChannelAgentBinding.agent_id == agent.id,
                    )
                )
                if binding is None:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ZALO_AGENT_MISMATCH",
                        "Kết nối Zalo không thuộc chatbot đã chọn.",
                    )
            try:
                verifier_ref = await self.vault.store(workspace_id=workspace_id, plaintext=verifier)
            except CredentialVaultError as exc:
                raise ApiError(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "CREDENTIAL_VAULT_UNAVAILABLE",
                    "Kho thông tin xác thực tạm thời không khả dụng.",
                ) from exc
            self.session.add(
                ChannelOAuthAttempt(
                    workspace_id=workspace_id,
                    user_id=user.id,
                    agent_id=agent.id,
                    revision_id=revision.id,
                    provider="zalo",
                    state_hash=hashlib.sha256(state.encode()).hexdigest(),
                    verifier_credential_ref=verifier_ref,
                    reauthorize_connection_id=payload.reauthorize_connection_id,
                    expires_at=expires_at,
                )
            )
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        query = urlencode(
            {
                "app_id": self.app_id,
                "redirect_uri": self.redirect_uri,
                "code_challenge": challenge,
                "state": state,
            }
        )
        return ZaloOAuthStartResponse(
            authorization_url=f"https://oauth.zaloapp.com/v4/oa/permission?{query}",
            expires_at=expires_at,
        )

    async def complete_oauth(
        self,
        user: User,
        *,
        state: str,
        code: str | None,
        oa_id: str | None,
        provider_error: str | None,
    ) -> UUID:
        if not state or len(state) > 256:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST, "ZALO_STATE_INVALID", "OAuth state không hợp lệ."
            )
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        now = datetime.now(UTC)
        async with self.session.begin():
            attempt = (
                await self.session.scalars(
                    select(ChannelOAuthAttempt)
                    .where(ChannelOAuthAttempt.state_hash == state_hash)
                    .with_for_update()
                )
            ).one_or_none()
            if (
                attempt is None
                or attempt.user_id != user.id
                or attempt.consumed_at is not None
                or self._aware(attempt.expires_at) <= now
            ):
                raise ApiError(
                    status.HTTP_400_BAD_REQUEST,
                    "ZALO_STATE_INVALID",
                    "Phiên kết nối Zalo đã hết hạn hoặc đã được sử dụng.",
                )
            attempt.consumed_at = now
            if provider_error is not None:
                attempt.safe_error_code = "ZALO_OAUTH_DENIED"
            workspace_id = attempt.workspace_id
            agent_id = attempt.agent_id
            revision_id = attempt.revision_id
            verifier_ref = attempt.verifier_credential_ref
            reauthorize_id = attempt.reauthorize_connection_id
        if provider_error is not None:
            if not await self._revoke_quietly(verifier_ref):
                await self._fail_attempt(state_hash, "ZALO_VERIFIER_CLEANUP_PENDING")
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "ZALO_OAUTH_DENIED",
                "Zalo không cấp quyền cho kết nối này.",
            )
        if not code or len(code) > 4096 or not oa_id or len(oa_id) > 255:
            await self._fail_attempt(state_hash, "ZALO_CALLBACK_INVALID")
            if not await self._revoke_quietly(verifier_ref):
                await self._fail_attempt(state_hash, "ZALO_VERIFIER_CLEANUP_PENDING")
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "ZALO_CALLBACK_INVALID",
                "Phản hồi OAuth từ Zalo không hợp lệ.",
            )
        credential_ref: str | None = None
        try:
            verifier = await self.vault.resolve(verifier_ref)
            token_set = await self.gateway.exchange_code(code=code, code_verifier=verifier)
            identity = await self.gateway.get_oa(token_set.access_token)
            if identity.oa_id != oa_id:
                raise ZaloProviderError("ZALO_OA_MISMATCH")
            webhook_secret: str | None = None
            if reauthorize_id is not None:
                old_ref = await self._credential_ref(workspace_id, reauthorize_id)
                if old_ref is not None:
                    try:
                        webhook_secret = decode_bundle(
                            await self.vault.resolve(old_ref)
                        ).webhook_secret
                    except (CredentialVaultError, ZaloCredentialError):
                        webhook_secret = None
            bundle = ZaloCredentialBundle(
                access_token=token_set.access_token,
                refresh_token=token_set.refresh_token,
                expires_at=datetime.now(UTC) + timedelta(seconds=token_set.expires_in),
                webhook_secret=webhook_secret,
            )
            credential_ref = await self.vault.store(
                workspace_id=workspace_id, plaintext=encode_bundle(bundle)
            )
            old_connection_ref = await self._persist_oauth_connection(
                workspace_id=workspace_id,
                agent_id=agent_id,
                revision_id=revision_id,
                reauthorize_id=reauthorize_id,
                identity_id=identity.oa_id,
                identity_name=identity.name,
                credential_ref=credential_ref,
                webhook_configured=webhook_secret is not None,
                state_hash=state_hash,
            )
        except CredentialVaultError as exc:
            await self._fail_attempt(state_hash, "CREDENTIAL_VAULT_UNAVAILABLE")
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CREDENTIAL_VAULT_UNAVAILABLE",
                "Kho thông tin xác thực tạm thời không khả dụng.",
            ) from exc
        except ZaloProviderError as exc:
            await self._fail_attempt(state_hash, exc.safe_code)
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                exc.safe_code,
                "Không thể hoàn tất xác thực Zalo OA.",
            ) from exc
        except (ApiError, IntegrityError) as exc:
            await self._fail_attempt(state_hash, "ZALO_CONNECTION_CONFLICT")
            if credential_ref is not None:
                await self._revoke_quietly(credential_ref)
            if isinstance(exc, ApiError):
                raise
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "ZALO_CONNECTION_CONFLICT",
                "Zalo OA này đã được kết nối.",
            ) from exc
        finally:
            if not await self._revoke_quietly(verifier_ref):
                await self._fail_attempt(state_hash, "ZALO_VERIFIER_CLEANUP_PENDING")
        if old_connection_ref is not None and old_connection_ref != credential_ref:
            await self._revoke_quietly(old_connection_ref)
        return workspace_id

    async def list(self, user: User, workspace_id: UUID) -> ZaloConnectionListResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=False)
            rows = list(
                (
                    await self.session.execute(
                        select(ChannelConnection, ChannelAgentBinding, Agent)
                        .join(
                            ChannelAgentBinding,
                            (ChannelAgentBinding.workspace_id == ChannelConnection.workspace_id)
                            & (ChannelAgentBinding.connection_id == ChannelConnection.id),
                        )
                        .join(
                            Agent,
                            (Agent.workspace_id == ChannelAgentBinding.workspace_id)
                            & (Agent.id == ChannelAgentBinding.agent_id),
                        )
                        .where(
                            ChannelConnection.workspace_id == workspace_id,
                            ChannelConnection.provider == "zalo",
                        )
                        .order_by(ChannelConnection.id)
                    )
                ).all()
            )
        items: list[ZaloConnectionResponse] = []
        for connection, _, agent in rows:
            configured = False
            if connection.credential_ref is not None:
                try:
                    configured = (
                        decode_bundle(
                            await self.vault.resolve(connection.credential_ref)
                        ).webhook_secret
                        is not None
                    )
                except (CredentialVaultError, ZaloCredentialError):
                    configured = False
            assert connection.external_account_id is not None
            items.append(
                ZaloConnectionResponse(
                    id=connection.id,
                    display_name=connection.display_name,
                    external_account_id=connection.external_account_id,
                    lifecycle_state=cast(ConnectionState, connection.lifecycle_state),
                    health_state=cast(HealthState, connection.health_state),
                    webhook_configured=configured,
                    agent_public_id=agent.public_id,
                    agent_name=agent.name,
                    last_verified_at=connection.last_verified_at,
                    created_at=connection.created_at,
                    updated_at=connection.updated_at,
                )
            )
        return ZaloConnectionListResponse(items=items)

    async def set_webhook_secret(
        self, user: User, workspace_id: UUID, connection_id: int, secret: str
    ) -> ZaloConnectionResponse:
        if len(secret.encode()) < 16 or len(secret) > 4096:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "ZALO_WEBHOOK_SECRET_INVALID",
                "OA secret key không hợp lệ.",
            )
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=True)
            old_ref = connection.credential_ref
        if old_ref is None:
            raise ApiError(
                status.HTTP_409_CONFLICT, "ZALO_REAUTH_REQUIRED", "Cần kết nối lại Zalo OA."
            )
        try:
            bundle = decode_bundle(await self.vault.resolve(old_ref))
            new_ref = await self.vault.store(
                workspace_id=workspace_id,
                plaintext=encode_bundle(
                    ZaloCredentialBundle(
                        access_token=bundle.access_token,
                        refresh_token=bundle.refresh_token,
                        expires_at=bundle.expires_at,
                        webhook_secret=secret,
                    )
                ),
            )
        except (CredentialVaultError, ZaloCredentialError) as exc:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CREDENTIAL_VAULT_UNAVAILABLE",
                "Kho thông tin xác thực tạm thời không khả dụng.",
            ) from exc
        async with self.session.begin():
            connection = await self._connection(workspace_id, connection_id, active=True)
            if connection.credential_ref != old_ref:
                await self._revoke_quietly(new_ref)
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "ZALO_CREDENTIAL_CHANGED",
                    "Thông tin xác thực vừa được cập nhật; vui lòng thử lại.",
                )
            connection.credential_ref = new_ref
            connection.health_state = "healthy"
            connection.updated_at = datetime.now(UTC)
        await self._revoke_quietly(old_ref)
        listed = await self.list(user, workspace_id)
        return next(item for item in listed.items if item.id == connection_id)

    async def verify_health(
        self, user: User, workspace_id: UUID, connection_id: int
    ) -> ZaloConnectionResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=True)
            expected_id = connection.external_account_id
        try:
            token = await self.tokens.access_token(connection_id=connection_id)
            identity = await self.gateway.get_oa(token)
            if identity.oa_id != expected_id:
                raise ZaloProviderError("ZALO_OA_MISMATCH")
        except (ZaloTokenError, ZaloProviderError) as exc:
            async with self.session.begin():
                connection = await self._connection(workspace_id, connection_id, active=True)
                connection.health_state = "reauth_required"
                connection.updated_at = datetime.now(UTC)
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "ZALO_REAUTH_REQUIRED",
                "Zalo OA cần được xác thực lại.",
            ) from exc
        async with self.session.begin():
            connection = await self._connection(workspace_id, connection_id, active=True)
            assert connection.credential_ref is not None
            try:
                configured = (
                    decode_bundle(
                        await self.vault.resolve(connection.credential_ref)
                    ).webhook_secret
                    is not None
                )
            except (CredentialVaultError, ZaloCredentialError):
                configured = False
            connection.display_name = identity.name
            connection.health_state = "healthy" if configured else "webhook_subscription_failure"
            connection.last_verified_at = datetime.now(UTC)
            connection.updated_at = datetime.now(UTC)
        listed = await self.list(user, workspace_id)
        return next(item for item in listed.items if item.id == connection_id)

    async def revoke(self, user: User, workspace_id: UUID, connection_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=True)
            credential_ref = connection.credential_ref
            connection.credential_ref = None
            connection.lifecycle_state = "revoked"
            connection.health_state = "reauth_required"
            connection.updated_at = datetime.now(UTC)
            binding = await self.session.scalar(
                select(ChannelAgentBinding).where(
                    ChannelAgentBinding.workspace_id == workspace_id,
                    ChannelAgentBinding.connection_id == connection_id,
                )
            )
            if binding is not None:
                binding.enabled = False
                binding.updated_at = datetime.now(UTC)
        if credential_ref is not None:
            await self._revoke_quietly(credential_ref)

    async def _persist_oauth_connection(
        self,
        *,
        workspace_id: UUID,
        agent_id: int,
        revision_id: int,
        reauthorize_id: int | None,
        identity_id: str,
        identity_name: str,
        credential_ref: str,
        webhook_configured: bool,
        state_hash: str,
    ) -> str | None:
        async with self.session.begin():
            existing = (
                await self.session.scalars(
                    select(ChannelConnection)
                    .where(
                        ChannelConnection.provider == "zalo",
                        ChannelConnection.external_account_id == identity_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            old_ref: str | None = None
            reactivating_revoked = False
            if reauthorize_id is not None:
                connection = await self._connection(workspace_id, reauthorize_id, active=True)
                if connection.external_account_id != identity_id:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ZALO_OA_MISMATCH",
                        "OAuth không thuộc Zalo OA đang kết nối.",
                    )
                old_ref = connection.credential_ref
            elif existing is not None:
                if existing.workspace_id != workspace_id or existing.lifecycle_state == "active":
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ZALO_CONNECTION_CONFLICT",
                        "Zalo OA này đã được kết nối.",
                    )
                connection = existing
                old_ref = connection.credential_ref
                reactivating_revoked = True
            else:
                connection = ChannelConnection(
                    workspace_id=workspace_id,
                    provider="zalo",
                    display_name=identity_name,
                    external_account_id=identity_id,
                )
                self.session.add(connection)
                await self.session.flush()
            connection.display_name = identity_name
            connection.credential_ref = credential_ref
            connection.lifecycle_state = "active"
            connection.health_state = (
                "healthy" if webhook_configured else "webhook_subscription_failure"
            )
            connection.last_verified_at = datetime.now(UTC)
            connection.updated_at = datetime.now(UTC)
            binding = await self.session.scalar(
                select(ChannelAgentBinding)
                .where(ChannelAgentBinding.connection_id == connection.id)
                .with_for_update()
            )
            if binding is None:
                self.session.add(
                    ChannelAgentBinding(
                        workspace_id=workspace_id,
                        connection_id=connection.id,
                        agent_id=agent_id,
                        active_revision_id=revision_id,
                        enabled=True,
                    )
                )
            else:
                if binding.workspace_id != workspace_id:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ZALO_AGENT_MISMATCH",
                        "Kết nối Zalo không thuộc chatbot đã chọn.",
                    )
                if binding.agent_id != agent_id and not reactivating_revoked:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "ZALO_AGENT_MISMATCH",
                        "Kết nối Zalo không thuộc chatbot đã chọn.",
                    )
                binding.agent_id = agent_id
                binding.active_revision_id = revision_id
                binding.enabled = True
                binding.updated_at = datetime.now(UTC)
            attempt = await self.session.scalar(
                select(ChannelOAuthAttempt)
                .where(ChannelOAuthAttempt.state_hash == state_hash)
                .with_for_update()
            )
            if attempt is None or attempt.workspace_id != workspace_id:
                raise ApiError(
                    status.HTTP_409_CONFLICT, "ZALO_STATE_INVALID", "OAuth state không hợp lệ."
                )
            attempt.succeeded = True
            attempt.safe_error_code = None
            return old_ref

    async def _credential_ref(self, workspace_id: UUID, connection_id: int) -> str | None:
        async with self.session.begin():
            connection = await self._connection(workspace_id, connection_id, active=True)
            return connection.credential_ref

    async def _fail_attempt(self, state_hash: str, code: str) -> None:
        await self.session.rollback()
        async with self.session.begin():
            attempt = await self.session.scalar(
                select(ChannelOAuthAttempt)
                .where(ChannelOAuthAttempt.state_hash == state_hash)
                .with_for_update()
            )
            if attempt is not None:
                attempt.safe_error_code = code[:80]

    async def _connection(
        self, workspace_id: UUID, connection_id: int, *, active: bool
    ) -> ChannelConnection:
        statement = select(ChannelConnection).where(
            ChannelConnection.workspace_id == workspace_id,
            ChannelConnection.id == connection_id,
            ChannelConnection.provider == "zalo",
        )
        if active:
            statement = statement.where(ChannelConnection.lifecycle_state == "active")
        statement = statement.execution_options(populate_existing=True)
        connection = (await self.session.scalars(statement)).one_or_none()
        if connection is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy kết nối Zalo.")
        return connection

    async def _revoke_quietly(self, credential_ref: str) -> bool:
        try:
            await self.vault.revoke(credential_ref)
        except CredentialVaultError:
            logger.warning("zalo_credential_cleanup_failed")
            return False
        return True

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
