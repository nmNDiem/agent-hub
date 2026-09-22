import hmac
from dataclasses import dataclass
from time import monotonic
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.email_delivery import EmailDelivery, UnavailableEmailDelivery
from agent_hub_api.identity.models import User
from agent_hub_api.identity.security import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    decode_access_token,
    hash_rate_limit_key,
)
from agent_hub_api.identity.service import AuthService


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_email_delivery(request: Request) -> EmailDelivery:
    delivery: EmailDelivery | None = getattr(request.app.state, "email_delivery", None)
    return delivery or UnavailableEmailDelivery()


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    if access_token is None:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "UNAUTHENTICATED", "Vui lòng đăng nhập.")
    settings = get_request_settings(request)
    try:
        payload = decode_access_token(access_token, settings)
        user_id = UUID(str(payload["sub"]))
        session_id = int(payload["sid"])
    except (jwt.PyJWTError, ValueError, TypeError, RuntimeError) as exc:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "INVALID_SESSION", "Phiên đã hết hạn."
        ) from exc
    return await AuthService(session, settings).authenticate_access(user_id, session_id)


def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
) -> None:
    csrf_header = request.headers.get(CSRF_HEADER)
    if (
        csrf_cookie is None
        or csrf_header is None
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise ApiError(status.HTTP_403_FORBIDDEN, "CSRF_FAILED", "Yêu cầu không hợp lệ.")
    require_allowed_origin(request)


def require_allowed_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    settings = get_request_settings(request)
    if origin is not None and origin.rstrip("/") not in settings.allowed_origins:
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "ORIGIN_DENIED", "Nguồn yêu cầu không hợp lệ."
        )


@dataclass
class RateLimitBucket:
    window_started: float
    attempts: int


class LoginRateLimiter:
    """Small local-runtime guard; production multi-instance rate limiting remains an ops concern."""

    def __init__(
        self, *, limit: int = 8, window_seconds: int = 300, max_buckets: int = 10_000
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._buckets: dict[str, RateLimitBucket] = {}

    def check(self, *, email: str, client_host: str, signing_key: str) -> None:
        now = monotonic()
        if len(self._buckets) >= self.max_buckets:
            self._buckets = {
                key: value
                for key, value in self._buckets.items()
                if now - value.window_started < self.window_seconds
            }
            if len(self._buckets) >= self.max_buckets:
                self._buckets.pop(next(iter(self._buckets)))
        key = hash_rate_limit_key(f"{client_host}:{email.casefold()}", signing_key)
        bucket = self._buckets.get(key)
        if bucket is None or now - bucket.window_started >= self.window_seconds:
            self._buckets[key] = RateLimitBucket(window_started=now, attempts=1)
            return
        if bucket.attempts >= self.limit:
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "RATE_LIMITED",
                "Quá nhiều lần thử. Vui lòng thử lại sau.",
            )
        bucket.attempts += 1
