from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.config import Settings
from agent_hub_api.email_delivery import EmailDelivery
from agent_hub_api.errors import ApiError
from agent_hub_api.identifiers import new_uuid_v7
from agent_hub_api.models import AuthSession, EmailToken, User, Workspace, WorkspaceMember
from agent_hub_api.schemas import (
    CreateWorkspaceRequest,
    MeResponse,
    UpdateWorkspaceRequest,
    UserResponse,
    WorkspaceResponse,
)
from agent_hub_api.security import (
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


WorkspaceRole = Literal["owner", "admin", "member"]


def workspace_response(workspace: Workspace, role: str) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=workspace.id,
        slug=workspace.slug,
        display_name=workspace.display_name,
        timezone=workspace.timezone,
        role=cast(WorkspaceRole, role),
        created_at=workspace.created_at,
    )


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def register(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = User(
            id=new_uuid_v7(),
            normalized_email=normalize_email(email),
            password_hash=hash_password(password),
            status="active",
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "ACCOUNT_UNAVAILABLE",
                "Không thể tạo tài khoản với thông tin đã cung cấp.",
            ) from exc
        tokens = await self._create_session(user)
        await self.session.commit()
        return user, tokens

    async def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        normalized_email = normalize_email(email)
        user = await self.session.scalar(
            select(User).where(User.normalized_email == normalized_email)
        )
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        password_matches = verify_password(password, password_hash)
        if user is None or not password_matches or user.status != "active":
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)
        tokens = await self._create_session(user)
        await self.session.commit()
        return user, tokens

    async def refresh(self, refresh_token: str) -> tuple[User, TokenPair]:
        token_hash = hash_opaque_token(refresh_token)
        auth_session = await self.session.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == token_hash)
            .with_for_update()
        )
        if auth_session is None:
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")
        if auth_session.revoked_at is not None:
            await self._revoke_family(auth_session.family_key)
            await self.session.commit()
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "SESSION_REPLAY", "Phiên đã bị thu hồi.")
        if is_expired(auth_session.expires_at):
            auth_session.revoked_at = datetime.now(UTC)
            await self.session.commit()
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")

        user = await self.session.get(User, auth_session.user_id)
        if user is None or user.status != "active":
            await self._revoke_family(auth_session.family_key)
            await self.session.commit()
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")

        now = datetime.now(UTC)
        auth_session.revoked_at = now
        tokens = await self._create_session(
            user,
            family_key=auth_session.family_key,
            rotated_from_id=auth_session.id,
        )
        await self.session.commit()
        return user, tokens

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token is not None:
            auth_session = await self.session.scalar(
                select(AuthSession).where(
                    AuthSession.refresh_token_hash == hash_opaque_token(refresh_token)
                )
            )
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = datetime.now(UTC)
        await self.session.commit()

    async def authenticate_access(self, user_id: UUID, session_id: int) -> User:
        result = await self.session.execute(
            select(User, AuthSession)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(User.id == user_id, AuthSession.id == session_id)
        )
        row = result.one_or_none()
        if row is None:
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")
        user, auth_session = row
        if (
            user.status != "active"
            or auth_session.revoked_at is not None
            or is_expired(auth_session.expires_at)
        ):
            raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")
        return user

    async def issue_email_token(self, *, user: User, purpose: str, lifetime: timedelta) -> str:
        await self.session.execute(
            update(EmailToken)
            .where(
                EmailToken.user_id == user.id,
                EmailToken.purpose == purpose,
                EmailToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        raw_token = generate_opaque_token()
        self.session.add(
            EmailToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_opaque_token(raw_token),
                expires_at=datetime.now(UTC) + lifetime,
            )
        )
        await self.session.commit()
        return raw_token

    async def request_password_reset(self, email: str, delivery: EmailDelivery) -> None:
        user = await self.session.scalar(
            select(User).where(User.normalized_email == normalize_email(email))
        )
        if user is None or user.status != "active":
            return
        token = await self.issue_email_token(
            user=user, purpose="reset_password", lifetime=timedelta(minutes=30)
        )
        await delivery.send_password_reset(recipient=user.normalized_email, token=token)

    async def consume_email_token(self, token: str, purpose: str) -> User:
        email_token = await self.session.scalar(
            select(EmailToken)
            .where(
                EmailToken.token_hash == hash_opaque_token(token),
                EmailToken.purpose == purpose,
            )
            .with_for_update()
        )
        if (
            email_token is None
            or email_token.used_at is not None
            or is_expired(email_token.expires_at)
        ):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN", "Liên kết không hợp lệ.")
        user = await self.session.get(User, email_token.user_id)
        if user is None or user.status != "active":
            raise ApiError(status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN", "Liên kết không hợp lệ.")
        email_token.used_at = datetime.now(UTC)
        return user

    async def verify_email(self, token: str) -> None:
        user = await self.consume_email_token(token, "verify_email")
        user.email_verified_at = datetime.now(UTC)
        await self.session.commit()

    async def reset_password(self, token: str, password: str) -> None:
        user = await self.consume_email_token(token, "reset_password")
        user.password_hash = hash_password(password)
        user.updated_at = datetime.now(UTC)
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.commit()

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
        self.session.add(auth_session)
        await self.session.flush()
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

    async def _revoke_family(self, family_key: str) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.family_key == family_key, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> list[WorkspaceResponse]:
        result = await self.session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id, Workspace.status == "active")
            .order_by(Workspace.created_at, Workspace.id)
        )
        return [workspace_response(workspace, role) for workspace, role in result.all()]

    async def me(self, user: User) -> MeResponse:
        return MeResponse(user=user_response(user), workspaces=await self.list_for_user(user.id))

    async def create(self, user: User, request: CreateWorkspaceRequest) -> WorkspaceResponse:
        workspace = Workspace(
            id=new_uuid_v7(),
            slug=request.slug,
            display_name=request.display_name,
            timezone=request.timezone,
        )
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "WORKSPACE_SLUG_UNAVAILABLE",
                "Đường dẫn cửa hàng đã được sử dụng.",
            ) from exc
        await self.session.refresh(workspace)
        return workspace_response(workspace, "owner")

    async def get_for_user(self, user_id: UUID, workspace_id: UUID) -> tuple[Workspace, str]:
        result = await self.session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
                Workspace.status == "active",
            )
        )
        row = result.one_or_none()
        if row is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy cửa hàng.",
            )
        return row._tuple()

    async def update(
        self, user: User, workspace_id: UUID, request: UpdateWorkspaceRequest
    ) -> WorkspaceResponse:
        workspace, role = await self.get_for_user(user.id, workspace_id)
        if role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền thay đổi cửa hàng này.",
            )
        workspace.display_name = request.display_name
        workspace.timezone = request.timezone
        workspace.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace_response(workspace, role)
