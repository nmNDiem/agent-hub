from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.channels.contracts import CredentialVault


class CredentialVaultError(RuntimeError):
    pass


class SupabaseCredentialVault(CredentialVault):
    """Server-only adapter for Supabase Vault's authenticated encrypted secrets."""

    _PREFIX = "supabase-vault:"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    @classmethod
    def _secret_id(cls, credential_ref: str) -> UUID:
        if not credential_ref.startswith(cls._PREFIX):
            raise CredentialVaultError("CREDENTIAL_REF_INVALID")
        try:
            return UUID(credential_ref.removeprefix(cls._PREFIX))
        except ValueError as exc:
            raise CredentialVaultError("CREDENTIAL_REF_INVALID") from exc

    async def store(self, *, workspace_id: UUID, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("Credential plaintext cannot be empty")
        secret_name = f"agenthub-channel-{workspace_id}-{uuid4()}"
        try:
            async with self.session_factory() as session, session.begin():
                secret_id = await session.scalar(
                    text(
                        "SELECT vault.create_secret(:secret, :name, :description)"
                    ),
                    {
                        "secret": plaintext,
                        "name": secret_name,
                        "description": "AgentHub channel credential",
                    },
                )
        except Exception as exc:
            raise CredentialVaultError("CREDENTIAL_STORE_FAILED") from exc
        if secret_id is None:
            raise CredentialVaultError("CREDENTIAL_STORE_FAILED")
        return f"{self._PREFIX}{secret_id}"

    async def resolve(self, credential_ref: str) -> str:
        secret_id = self._secret_id(credential_ref)
        try:
            async with self.session_factory() as session:
                value = await session.scalar(
                    text(
                        "SELECT decrypted_secret FROM vault.decrypted_secrets "
                        "WHERE id = :secret_id"
                    ),
                    {"secret_id": secret_id},
                )
        except Exception as exc:
            raise CredentialVaultError("CREDENTIAL_RESOLVE_FAILED") from exc
        if not isinstance(value, str) or not value:
            raise CredentialVaultError("CREDENTIAL_NOT_FOUND")
        return value

    async def revoke(self, credential_ref: str) -> None:
        secret_id = self._secret_id(credential_ref)
        try:
            async with self.session_factory() as session, session.begin():
                await session.execute(
                    text("DELETE FROM vault.secrets WHERE id = :secret_id"),
                    {"secret_id": secret_id},
                )
        except Exception as exc:
            raise CredentialVaultError("CREDENTIAL_REVOKE_FAILED") from exc
