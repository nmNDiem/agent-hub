import logging
from datetime import UTC, datetime
from typing import Literal, cast
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
    ChannelResponseJob,
    OutboundDelivery,
)
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.core.errors import ApiError
from agent_hub_api.facebook.contracts import FacebookGraphGateway, FacebookProviderError
from agent_hub_api.facebook.schemas import (
    FacebookConnectionCreateRequest,
    FacebookConnectionListResponse,
    FacebookConnectionReauthorizeRequest,
    FacebookConnectionResponse,
)
from agent_hub_api.identity.models import User
from agent_hub_api.workspaces.service import WorkspaceService

logger = logging.getLogger("agent_hub_api.facebook")


class FacebookConnectionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        vault: CredentialVault,
        graph: FacebookGraphGateway,
    ) -> None:
        self.session = session
        self.vault = vault
        self.graph = graph

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền quản lý kênh Facebook.",
            )

    async def _responses(
        self, connections: list[ChannelConnection]
    ) -> list[FacebookConnectionResponse]:
        if not connections:
            return []
        connection_ids = [item.id for item in connections]
        bindings = {
            binding.connection_id: agent
            for binding, agent in (
                await self.session.execute(
                    select(ChannelAgentBinding, Agent)
                    .join(
                        Agent,
                        (Agent.workspace_id == ChannelAgentBinding.workspace_id)
                        & (Agent.id == ChannelAgentBinding.agent_id),
                    )
                    .where(ChannelAgentBinding.connection_id.in_(connection_ids))
                )
            ).all()
        }
        latest_jobs: dict[int, ChannelResponseJob] = {}
        for job in await self.session.scalars(
            select(ChannelResponseJob)
            .where(ChannelResponseJob.connection_id.in_(connection_ids))
            .order_by(ChannelResponseJob.id.desc())
        ):
            latest_jobs.setdefault(job.connection_id, job)
        latest_deliveries: dict[int, OutboundDelivery] = {}
        for delivery in await self.session.scalars(
            select(OutboundDelivery)
            .where(OutboundDelivery.connection_id.in_(connection_ids))
            .order_by(OutboundDelivery.id.desc())
        ):
            latest_deliveries.setdefault(delivery.connection_id, delivery)

        responses: list[FacebookConnectionResponse] = []
        for connection in connections:
            assert connection.external_account_id is not None
            agent = bindings.get(connection.id)
            if agent is None:
                raise RuntimeError("Facebook connection binding is missing")
            latest_job = latest_jobs.get(connection.id)
            latest_delivery = latest_deliveries.get(connection.id)
            responses.append(
                FacebookConnectionResponse(
                    id=connection.id,
                    display_name=connection.display_name,
                    external_account_id=connection.external_account_id,
                    lifecycle_state=cast(LiteralConnectionState, connection.lifecycle_state),
                    health_state=cast(LiteralHealthState, connection.health_state),
                    agent_public_id=agent.public_id,
                    agent_name=agent.name,
                    latest_queue_state=(
                        cast(LiteralQueueState, latest_job.state)
                        if latest_job is not None
                        else None
                    ),
                    latest_delivery_state=(
                        cast(LiteralDeliveryState, latest_delivery.state)
                        if latest_delivery is not None
                        else None
                    ),
                    latest_safe_error_code=(
                        latest_delivery.safe_error_code
                        if latest_delivery is not None
                        and latest_delivery.safe_error_code is not None
                        else latest_job.safe_error_code
                        if latest_job is not None
                        else None
                    ),
                    last_verified_at=connection.last_verified_at,
                    created_at=connection.created_at,
                    updated_at=connection.updated_at,
                )
            )
        return responses

    async def list(self, user: User, workspace_id: UUID) -> FacebookConnectionListResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=False)
            connections = (
                await self.session.scalars(
                    select(ChannelConnection)
                    .where(
                        ChannelConnection.workspace_id == workspace_id,
                        ChannelConnection.provider == "facebook",
                    )
                    .order_by(ChannelConnection.id)
                )
            ).all()
        return FacebookConnectionListResponse(items=await self._responses(list(connections)))

    async def create(
        self,
        user: User,
        workspace_id: UUID,
        payload: FacebookConnectionCreateRequest,
    ) -> FacebookConnectionResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
        token = payload.page_access_token.get_secret_value()
        if not token or len(token) > 4096:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "FACEBOOK_TOKEN_INVALID",
                "Page access token không hợp lệ.",
            )
        try:
            page = await self.graph.validate_page_token(token)
        except FacebookProviderError as exc:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "FACEBOOK_TOKEN_INVALID",
                "Không thể xác thực Facebook Page access token.",
            ) from exc
        try:
            await self.graph.subscribe_page(page.page_id, token)
        except FacebookProviderError as exc:
            try:
                await self.graph.unsubscribe_page(page.page_id, token)
            except FacebookProviderError:
                logger.warning("facebook_unsubscribe_failed_after_subscription_error")
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FACEBOOK_SUBSCRIPTION_FAILED",
                "Không thể đăng ký webhook cho Facebook Page.",
            ) from exc

        credential_ref: str | None = None
        try:
            credential_ref = await self.vault.store(workspace_id=workspace_id, plaintext=token)
            async with self.session.begin():
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
                        "FACEBOOK_AGENT_NOT_READY",
                        "Agent phải được xuất bản trước khi kết nối Facebook.",
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
                        "FACEBOOK_AGENT_NOT_READY",
                        "Agent chưa có revision đã xuất bản.",
                    )
                now = datetime.now(UTC)
                connection = ChannelConnection(
                    workspace_id=workspace_id,
                    provider="facebook",
                    display_name=page.name,
                    external_account_id=page.page_id,
                    credential_ref=credential_ref,
                    lifecycle_state="active",
                    health_state="healthy",
                    last_verified_at=now,
                )
                self.session.add(connection)
                await self.session.flush()
                self.session.add(
                    ChannelAgentBinding(
                        workspace_id=workspace_id,
                        connection_id=connection.id,
                        agent_id=agent.id,
                        active_revision_id=revision.id,
                        enabled=True,
                    )
                )
        except (ApiError, IntegrityError) as exc:
            if credential_ref is not None:
                try:
                    await self.vault.revoke(credential_ref)
                except CredentialVaultError:
                    logger.warning("facebook_credential_cleanup_failed")
            try:
                await self.graph.unsubscribe_page(page.page_id, token)
            except FacebookProviderError:
                logger.warning("facebook_unsubscribe_failed_after_connection_rollback")
            if isinstance(exc, ApiError):
                raise
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "FACEBOOK_CONNECTION_CONFLICT",
                "Không thể kết nối Facebook Page này.",
            ) from exc
        except CredentialVaultError as exc:
            try:
                await self.graph.unsubscribe_page(page.page_id, token)
            except FacebookProviderError:
                logger.warning("facebook_unsubscribe_failed_after_vault_error")
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CREDENTIAL_VAULT_UNAVAILABLE",
                "Kho thông tin xác thực tạm thời không khả dụng.",
            ) from exc
        return (await self._responses([connection]))[0]

    async def verify_health(
        self, user: User, workspace_id: UUID, connection_id: int
    ) -> FacebookConnectionResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=True)
            credential_ref = connection.credential_ref
            expected_page_id = connection.external_account_id
        if credential_ref is None:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "FACEBOOK_REAUTH_REQUIRED",
                "Cần kết nối lại Facebook Page.",
            )
        try:
            token = await self.vault.resolve(credential_ref)
            page = await self.graph.validate_page_token(token)
            if page.page_id != expected_page_id:
                raise FacebookProviderError("FACEBOOK_PAGE_MISMATCH")
            await self.graph.subscribe_page(page.page_id, token)
        except (CredentialVaultError, FacebookProviderError) as exc:
            async with self.session.begin():
                connection = await self._connection(workspace_id, connection_id, active=True)
                connection.health_state = (
                    "permission_expired"
                    if isinstance(exc, FacebookProviderError)
                    and exc.safe_code == "FACEBOOK_PERMISSION_EXPIRED"
                    else "webhook_subscription_failure"
                    if isinstance(exc, FacebookProviderError)
                    and exc.safe_code == "FACEBOOK_SUBSCRIPTION_FAILED"
                    else "reauth_required"
                )
                connection.updated_at = datetime.now(UTC)
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "FACEBOOK_REAUTH_REQUIRED",
                "Facebook Page cần được xác thực lại.",
            ) from exc
        async with self.session.begin():
            connection = await self._connection(workspace_id, connection_id, active=True)
            now = datetime.now(UTC)
            connection.display_name = page.name
            connection.health_state = "healthy"
            connection.last_verified_at = now
            connection.updated_at = now
        return (await self._responses([connection]))[0]

    async def reauthorize(
        self,
        user: User,
        workspace_id: UUID,
        connection_id: int,
        payload: FacebookConnectionReauthorizeRequest,
    ) -> FacebookConnectionResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=True)
            expected_page_id = connection.external_account_id
            old_ref = connection.credential_ref
        token = payload.page_access_token.get_secret_value()
        if not token or len(token) > 4096:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "FACEBOOK_TOKEN_INVALID",
                "Page access token không hợp lệ.",
            )
        try:
            page = await self.graph.validate_page_token(token)
        except FacebookProviderError as exc:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                exc.safe_code,
                "Không thể xác thực Facebook Page access token.",
            ) from exc
        if page.page_id != expected_page_id:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "FACEBOOK_PAGE_MISMATCH",
                "Token không thuộc Facebook Page đang kết nối.",
            )
        try:
            await self.graph.subscribe_page(page.page_id, token)
        except FacebookProviderError as exc:
            async with self.session.begin():
                connection = await self._connection(workspace_id, connection_id, active=True)
                connection.health_state = "webhook_subscription_failure"
                connection.updated_at = datetime.now(UTC)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FACEBOOK_SUBSCRIPTION_FAILED",
                "Không thể đăng ký webhook cho Facebook Page.",
            ) from exc
        try:
            new_ref = await self.vault.store(workspace_id=workspace_id, plaintext=token)
        except CredentialVaultError as exc:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CREDENTIAL_VAULT_UNAVAILABLE",
                "Kho thông tin xác thực tạm thời không khả dụng.",
            ) from exc
        try:
            async with self.session.begin():
                connection = await self._connection(workspace_id, connection_id, active=True)
                if connection.external_account_id != page.page_id:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "FACEBOOK_PAGE_MISMATCH",
                        "Facebook Page đã thay đổi trong lúc xác thực.",
                    )
                now = datetime.now(UTC)
                connection.credential_ref = new_ref
                connection.display_name = page.name
                connection.health_state = "healthy"
                connection.last_verified_at = now
                connection.updated_at = now
        except Exception:
            try:
                await self.vault.revoke(new_ref)
            except CredentialVaultError:
                logger.warning("facebook_new_credential_cleanup_failed")
            raise
        if old_ref is not None and old_ref != new_ref:
            try:
                await self.vault.revoke(old_ref)
            except CredentialVaultError:
                logger.warning("facebook_old_credential_cleanup_failed")
        return (await self._responses([connection]))[0]

    async def revoke(self, user: User, workspace_id: UUID, connection_id: int) -> None:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            connection = await self._connection(workspace_id, connection_id, active=False)
            credential_ref = connection.credential_ref
            external_account_id = connection.external_account_id
            connection.lifecycle_state = "revoked"
            connection.health_state = "reauth_required"
            connection.updated_at = datetime.now(UTC)
            binding = (
                await self.session.scalars(
                    select(ChannelAgentBinding).where(
                        ChannelAgentBinding.workspace_id == workspace_id,
                        ChannelAgentBinding.connection_id == connection_id,
                    )
                )
            ).one_or_none()
            if binding is not None:
                binding.enabled = False
                binding.updated_at = datetime.now(UTC)
        token: str | None = None
        if credential_ref is not None:
            try:
                token = await self.vault.resolve(credential_ref)
            except CredentialVaultError:
                logger.warning("facebook_credential_resolve_failed_during_revoke")
        if token is not None and external_account_id is not None:
            try:
                await self.graph.unsubscribe_page(external_account_id, token)
            except FacebookProviderError:
                logger.warning("facebook_unsubscribe_failed_after_local_revoke")
        if credential_ref is not None:
            try:
                await self.vault.revoke(credential_ref)
            except CredentialVaultError as exc:
                raise ApiError(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "CREDENTIAL_REVOKE_FAILED",
                    "Kết nối đã bị vô hiệu hóa nhưng cần thử lại việc xóa credential.",
                ) from exc
            async with self.session.begin():
                connection = await self._connection(workspace_id, connection_id, active=False)
                if connection.credential_ref == credential_ref:
                    connection.credential_ref = None
                    connection.updated_at = datetime.now(UTC)

    async def _connection(
        self, workspace_id: UUID, connection_id: int, *, active: bool
    ) -> ChannelConnection:
        statement = select(ChannelConnection).where(
            ChannelConnection.workspace_id == workspace_id,
            ChannelConnection.id == connection_id,
            ChannelConnection.provider == "facebook",
        )
        if active:
            statement = statement.where(ChannelConnection.lifecycle_state == "active")
        connection = (await self.session.scalars(statement)).one_or_none()
        if connection is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy kết nối Facebook.",
            )
        return connection


LiteralConnectionState = Literal["active", "revoked"]
LiteralHealthState = Literal[
    "unknown",
    "healthy",
    "permission_expired",
    "reauth_required",
    "webhook_subscription_failure",
    "delivery_unknown",
]
LiteralQueueState = Literal[
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "failed_terminal",
    "suppressed",
]
LiteralDeliveryState = Literal[
    "queued",
    "sending",
    "accepted",
    "delivered",
    "failed_retryable",
    "failed_terminal",
]
