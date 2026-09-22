from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.dependencies import (
    LoginRateLimiter,
    get_email_delivery,
    get_request_settings,
    require_allowed_origin,
    require_csrf,
)
from agent_hub_api.identity.email_delivery import EmailDelivery
from agent_hub_api.identity.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenRequest,
)
from agent_hub_api.identity.security import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, TokenPair
from agent_hub_api.identity.service import AuthService, user_response

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _set_session_cookies(response: Response, tokens: TokenPair, settings: Settings) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        tokens.csrf_token,
        max_age=settings.refresh_token_days * 86400,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=settings.cookie_secure, samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/v1/auth",
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.cookie_secure, samesite="lax")


def _limit_login(request: Request, email: str, settings: Settings) -> None:
    if settings.jwt_signing_key is None:
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AUTH_NOT_CONFIGURED",
            "Xác thực chưa được cấu hình.",
        )
    limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    limiter.check(
        email=email,
        client_host=request.client.host if request.client else "unknown",
        signing_key=settings.jwt_signing_key,
    )


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_allowed_origin)],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    delivery: Annotated[EmailDelivery, Depends(get_email_delivery)],
) -> SessionResponse:
    _limit_login(request, str(payload.email), settings)
    service = AuthService(session, settings)
    user, tokens = await service.register(str(payload.email), payload.password)
    if settings.email_delivery_enabled:
        verification_token = await service.issue_email_token(
            user=user, purpose="verify_email", lifetime=timedelta(hours=24)
        )
        await delivery.send_verification(recipient=user.normalized_email, token=verification_token)
    _set_session_cookies(response, tokens, settings)
    return SessionResponse(
        user=user_response(user),
        csrf_token=tokens.csrf_token,
        access_expires_at=tokens.access_expires_at,
    )


@router.post(
    "/login", response_model=SessionResponse, dependencies=[Depends(require_allowed_origin)]
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> SessionResponse:
    _limit_login(request, str(payload.email), settings)
    user, tokens = await AuthService(session, settings).login(str(payload.email), payload.password)
    _set_session_cookies(response, tokens, settings)
    return SessionResponse(
        user=user_response(user),
        csrf_token=tokens.csrf_token,
        access_expires_at=tokens.access_expires_at,
    )


@router.post("/refresh", response_model=SessionResponse, dependencies=[Depends(require_csrf)])
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> SessionResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token is None:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn.")
    user, tokens = await AuthService(session, settings).refresh(refresh_token)
    _set_session_cookies(response, tokens, settings)
    return SessionResponse(
        user=user_response(user),
        csrf_token=tokens.csrf_token,
        access_expires_at=tokens.access_expires_at,
    )


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> None:
    await AuthService(session, settings).logout(request.cookies.get(REFRESH_COOKIE))
    _clear_session_cookies(response, settings)


email_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@email_router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(require_allowed_origin)],
)
async def verify_email(
    payload: TokenRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> MessageResponse:
    await AuthService(session, settings).verify_email(payload.token)
    return MessageResponse(message="Email đã được xác minh.")


@email_router.post(
    "/forgot-password",
    response_model=MessageResponse,
    dependencies=[Depends(require_allowed_origin)],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    delivery: Annotated[EmailDelivery, Depends(get_email_delivery)],
) -> MessageResponse:
    _limit_login(request, str(payload.email), settings)
    await AuthService(session, settings).request_password_reset(str(payload.email), delivery)
    return MessageResponse(
        message="Nếu tài khoản tồn tại, hướng dẫn khôi phục sẽ được gửi qua email."
    )


@email_router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(require_allowed_origin)],
)
async def reset_password(
    payload: ResetPasswordRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> MessageResponse:
    await AuthService(session, settings).reset_password(payload.token, payload.password)
    return MessageResponse(message="Mật khẩu đã được cập nhật. Vui lòng đăng nhập lại.")
