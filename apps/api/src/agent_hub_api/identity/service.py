from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.identity.email_delivery import EmailDelivery
from agent_hub_api.identity.models import AuthSession, EmailToken, User
from agent_hub_api.identity.repository import IdentityRepository
from agent_hub_api.identity.schemas import UserResponse
from agent_hub_api.identity.security import (
    TokenPair,
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    is_expired,
    normalize_email,
    verify_password,
)

INVALID_CREDENTIALS = "Email hoặc mật khẩu không đúng."
DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-123")


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.normalized_email,
        email_verified=user.email_verified_at is not None,
    )


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = IdentityRepository(session)

    async def register(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = User(
            id=new_uuid_v7(),
            normalized_email=normalize_email(email),
            password_hash=hash_password(password),
            status="active",
        )
        try:
            async with self.session.begin():
                await self.repository.add_user(user)
                tokens = await self._create_session(user)
        except IntegrityError as exc:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "ACCOUNT_UNAVAILABLE",
                "Không thể tạo tài khoản với thông tin đã cung cấp.",
            ) from exc
        return user, tokens

    async def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        async with self.session.begin():
            user = await self.repository.get_user_by_email(normalize_email(email))
            password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
            password_matches = verify_password(password, password_hash)
            if user is None or not password_matches or user.status != "active":
                raise ApiError(
                    status.HTTP_401_UNAUTHORIZED,
                    "INVALID_CREDENTIALS",
                    INVALID_CREDENTIALS,
                )
            tokens = await self._create_session(user)
        return user, tokens

    async def refresh(self, refresh_token: str) -> tuple[User, TokenPair]:
        failure: ApiError | None = None
        user: User | None = None
        tokens: TokenPair | None = None
        async with self.session.begin():
            auth_session = await self.repository.get_auth_session_by_refresh_hash(
                hash_opaque_token(refresh_token), for_update=True
            )
            if auth_session is None:
                raise ApiError(
                    status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
                )
            if auth_session.revoked_at is not None:
                await self.repository.revoke_family(auth_session.family_key, datetime.now(UTC))
                failure = ApiError(
                    status.HTTP_401_UNAUTHORIZED, "SESSION_REPLAY", "Phiên đã bị thu hồi."
                )
            elif is_expired(auth_session.expires_at):
                auth_session.revoked_at = datetime.now(UTC)
                failure = ApiError(
                    status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
                )
            else:
                user = await self.repository.get_user(auth_session.user_id)
                if user is None or user.status != "active":
                    await self.repository.revoke_family(auth_session.family_key, datetime.now(UTC))
                    failure = ApiError(
                        status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
                    )
                else:
                    auth_session.revoked_at = datetime.now(UTC)
                    tokens = await self._create_session(
                        user,
                        family_key=auth_session.family_key,
                        rotated_from_id=auth_session.id,
                    )
        if failure is not None:
            raise failure
        if user is None or tokens is None:
            raise RuntimeError("Refresh transaction completed without a session result")
        return user, tokens

    async def logout(self, refresh_token: str | None) -> None:
        async with self.session.begin():
            if refresh_token is None:
                return
            auth_session = await self.repository.get_auth_session_by_refresh_hash(
                hash_opaque_token(refresh_token)
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = datetime.now(UTC)

    async def authenticate_access(self, user_id: UUID, session_id: int) -> User:
        async with self.session.begin():
            identity = await self.repository.get_access_identity(user_id, session_id)
            if identity is None:
                raise ApiError(
                    status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
                )
            user, auth_session = identity
            if (
                user.status != "active"
                or auth_session.revoked_at is not None
                or is_expired(auth_session.expires_at)
            ):
                raise ApiError(
                    status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
                )
        return user

    async def issue_email_token(self, *, user: User, purpose: str, lifetime: timedelta) -> str:
        async with self.session.begin():
            return await self._issue_email_token(user=user, purpose=purpose, lifetime=lifetime)

    async def request_password_reset(self, email: str, delivery: EmailDelivery) -> None:
        token: str | None = None
        recipient: str | None = None
        async with self.session.begin():
            user = await self.repository.get_user_by_email(normalize_email(email))
            if user is not None and user.status == "active":
                token = await self._issue_email_token(
                    user=user,
                    purpose="reset_password",
                    lifetime=timedelta(minutes=30),
                )
                recipient = user.normalized_email
        if token is not None and recipient is not None:
            await delivery.send_password_reset(recipient=recipient, token=token)

    async def verify_email(self, token: str) -> None:
        async with self.session.begin():
            user = await self._consume_email_token(token, "verify_email")
            user.email_verified_at = datetime.now(UTC)

    async def reset_password(self, token: str, password: str) -> None:
        async with self.session.begin():
            user = await self._consume_email_token(token, "reset_password")
            now = datetime.now(UTC)
            user.password_hash = hash_password(password)
            user.updated_at = now
            await self.repository.revoke_user_sessions(user.id, now)

    async def _issue_email_token(
        self, *, user: User, purpose: str, lifetime: timedelta
    ) -> str:
        now = datetime.now(UTC)
        await self.repository.invalidate_email_tokens(
            user_id=user.id, purpose=purpose, used_at=now
        )
        raw_token = generate_opaque_token()
        self.repository.add_email_token(
            EmailToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_opaque_token(raw_token),
                expires_at=now + lifetime,
            )
        )
        return raw_token

    async def _consume_email_token(self, token: str, purpose: str) -> User:
        email_token = await self.repository.get_email_token_for_update(
            hash_opaque_token(token), purpose
        )
        if (
            email_token is None
            or email_token.used_at is not None
            or is_expired(email_token.expires_at)
        ):
            raise ApiError(
                status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN", "Liên kết không hợp lệ."
            )
        user = await self.repository.get_user(email_token.user_id)
        if user is None or user.status != "active":
            raise ApiError(
                status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN", "Liên kết không hợp lệ."
            )
        email_token.used_at = datetime.now(UTC)
        return user

    async def _create_session(
        self,
        user: User,
        *,
        family_key: str | None = None,
        rotated_from_id: int | None = None,
    ) -> TokenPair:
        if self.settings.jwt_signing_key is None:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "AUTH_NOT_CONFIGURED",
                "Xác thực chưa được cấu hình.",
            )
        refresh_token = generate_opaque_token()
        refresh_expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_days)
        auth_session = AuthSession(
            user_id=user.id,
            refresh_token_hash=hash_opaque_token(refresh_token),
            family_key=family_key or hash_opaque_token(generate_opaque_token()),
            expires_at=refresh_expires_at,
            rotated_from_id=rotated_from_id,
        )
        await self.repository.add_auth_session(auth_session)
        access_token, access_expires_at = create_access_token(
            user_id=user.id, session_id=auth_session.id, settings=self.settings
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=generate_opaque_token(),
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )
