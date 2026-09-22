from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.identity.models import AuthSession, EmailToken, User


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_user(self, user: User) -> None:
        self.session.add(user)
        await self.session.flush()

    async def get_user_by_email(self, normalized_email: str) -> User | None:
        return cast(
            User | None,
            await self.session.scalar(
                select(User).where(User.normalized_email == normalized_email)
            ),
        )

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def add_auth_session(self, auth_session: AuthSession) -> None:
        self.session.add(auth_session)
        await self.session.flush()

    async def get_auth_session_by_refresh_hash(
        self, token_hash: str, *, for_update: bool = False
    ) -> AuthSession | None:
        query = select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        if for_update:
            query = query.with_for_update()
        return cast(AuthSession | None, await self.session.scalar(query))

    async def get_access_identity(
        self, user_id: UUID, session_id: int
    ) -> tuple[User, AuthSession] | None:
        result = await self.session.execute(
            select(User, AuthSession)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(User.id == user_id, AuthSession.id == session_id)
        )
        row = result.one_or_none()
        return row._tuple() if row is not None else None

    async def revoke_family(self, family_key: str, revoked_at: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.family_key == family_key, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )

    async def invalidate_email_tokens(
        self, *, user_id: UUID, purpose: str, used_at: datetime
    ) -> None:
        await self.session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user_id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=used_at)
        )

    def add_email_token(self, email_token: EmailToken) -> None:
        self.session.add(email_token)

    async def get_email_token_for_update(
        self, token_hash: str, purpose: str
    ) -> EmailToken | None:
        return cast(
            EmailToken | None,
            await self.session.scalar(
                select(EmailToken)
                .where(EmailToken.token_hash == token_hash, EmailToken.purpose == purpose)
                .with_for_update()
            ),
        )

    async def revoke_user_sessions(self, user_id: UUID, revoked_at: datetime) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
