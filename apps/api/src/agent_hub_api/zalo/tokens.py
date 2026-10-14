import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.channels.contracts import CredentialVault
from agent_hub_api.channels.models import ChannelConnection, ChannelOAuthAttempt
from agent_hub_api.channels.vault import CredentialVaultError
from agent_hub_api.zalo.contracts import ZaloCredentialBundle, ZaloGateway, ZaloProviderError
from agent_hub_api.zalo.credentials import ZaloCredentialError, decode_bundle, encode_bundle

logger = logging.getLogger("agent_hub_api.zalo.tokens")


class ZaloTokenError(RuntimeError):
    def __init__(self, safe_code: str, *, retryable: bool = False) -> None:
        super().__init__(safe_code)
        self.safe_code = safe_code
        self.retryable = retryable


class ZaloTokenManager:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        vault: CredentialVault,
        gateway: ZaloGateway,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self.session_factory = session_factory
        self.vault = vault
        self.gateway = gateway
        self.refresh_margin = timedelta(seconds=refresh_margin_seconds)

    async def access_token(self, *, connection_id: int) -> str:
        old_ref: str | None = None
        async with self.session_factory() as session, session.begin():
            connection = (
                await session.scalars(
                    select(ChannelConnection)
                    .where(
                        ChannelConnection.id == connection_id,
                        ChannelConnection.provider == "zalo",
                        ChannelConnection.lifecycle_state == "active",
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if connection is None or connection.credential_ref is None:
                raise ZaloTokenError("ZALO_REAUTH_REQUIRED")
            old_ref = connection.credential_ref
            try:
                bundle = decode_bundle(await self.vault.resolve(old_ref))
            except CredentialVaultError as exc:
                if str(exc) == "CREDENTIAL_RESOLVE_FAILED":
                    raise ZaloTokenError("CREDENTIAL_VAULT_UNAVAILABLE", retryable=True) from exc
                connection.health_state = "reauth_required"
                raise ZaloTokenError("ZALO_REAUTH_REQUIRED") from exc
            except ZaloCredentialError as exc:
                connection.health_state = "reauth_required"
                raise ZaloTokenError("ZALO_REAUTH_REQUIRED") from exc
            if bundle.expires_at > datetime.now(UTC) + self.refresh_margin:
                return bundle.access_token
            try:
                refreshed = await self.gateway.refresh_token(bundle.refresh_token)
                new_bundle = ZaloCredentialBundle(
                    access_token=refreshed.access_token,
                    refresh_token=refreshed.refresh_token,
                    expires_at=datetime.now(UTC) + timedelta(seconds=refreshed.expires_in),
                    webhook_secret=bundle.webhook_secret,
                )
                new_ref = await self.vault.store(
                    workspace_id=connection.workspace_id,
                    plaintext=encode_bundle(new_bundle),
                )
            except ZaloProviderError as exc:
                if not exc.retryable:
                    connection.health_state = "reauth_required"
                raise ZaloTokenError(exc.safe_code, retryable=exc.retryable) from exc
            except CredentialVaultError as exc:
                raise ZaloTokenError("CREDENTIAL_VAULT_UNAVAILABLE", retryable=True) from exc
            connection.credential_ref = new_ref
            connection.health_state = (
                "healthy"
                if new_bundle.webhook_secret is not None
                else "webhook_subscription_failure"
            )
            connection.last_verified_at = datetime.now(UTC)
            connection.updated_at = datetime.now(UTC)
        if old_ref is not None:
            try:
                await self.vault.revoke(old_ref)
            except CredentialVaultError:
                logger.warning("zalo_old_credential_cleanup_failed")
        return new_bundle.access_token


class ZaloOAuthAttemptCleanup:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        vault: CredentialVault,
    ) -> None:
        self.session_factory = session_factory
        self.vault = vault

    async def run_once(self, *, now: datetime | None = None) -> bool:
        cleanup_time = now or datetime.now(UTC)
        async with self.session_factory() as session, session.begin():
            attempt = (
                await session.scalars(
                    select(ChannelOAuthAttempt)
                    .where(
                        ChannelOAuthAttempt.provider == "zalo",
                        or_(
                            (
                                ChannelOAuthAttempt.consumed_at.is_(None)
                                & (ChannelOAuthAttempt.expires_at <= cleanup_time)
                            ),
                            ChannelOAuthAttempt.safe_error_code == "ZALO_VERIFIER_CLEANUP_PENDING",
                        ),
                    )
                    .order_by(ChannelOAuthAttempt.expires_at, ChannelOAuthAttempt.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).one_or_none()
            if attempt is None:
                return False
            attempt_id = attempt.id
            verifier_ref = attempt.verifier_credential_ref
        try:
            await self.vault.revoke(verifier_ref)
        except CredentialVaultError:
            logger.warning("zalo_oauth_verifier_cleanup_failed")
            return False
        async with self.session_factory() as session, session.begin():
            attempt = await session.get(ChannelOAuthAttempt, attempt_id, with_for_update=True)
            if attempt is not None:
                if attempt.consumed_at is None:
                    attempt.consumed_at = cleanup_time
                    attempt.safe_error_code = "ZALO_STATE_EXPIRED"
                elif attempt.safe_error_code == "ZALO_VERIFIER_CLEANUP_PENDING":
                    attempt.safe_error_code = None if attempt.succeeded else "ZALO_OAUTH_FAILED"
        return True
