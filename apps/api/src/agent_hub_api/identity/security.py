import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from agent_hub_api.core.config import Settings

ACCESS_COOKIE = "agenthub_access"
REFRESH_COOKIE = "agenthub_refresh"
CSRF_COOKIE = "agenthub_csrf"
CSRF_HEADER = "x-csrf-token"
JWT_ALGORITHM = "HS256"

password_hasher = PasswordHash.recommended()


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    csrf_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


def normalize_email(value: str) -> str:
    local, separator, domain = value.strip().partition("@")
    if not separator:
        return value.strip().casefold()
    return f"{local.casefold()}@{domain.casefold()}"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_rate_limit_key(value: str, signing_key: str) -> str:
    return hmac.new(signing_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_access_token(
    *, user_id: UUID, session_id: int, settings: Settings
) -> tuple[str, datetime]:
    if settings.jwt_signing_key is None:
        raise RuntimeError("JWT signing key is not configured")
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": session_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    encoded = jwt.encode(payload, settings.jwt_signing_key, algorithm=JWT_ALGORITHM)
    return encoded, expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    if settings.jwt_signing_key is None:
        raise RuntimeError("JWT signing key is not configured")
    return jwt.decode(
        token,
        settings.jwt_signing_key,
        algorithms=[JWT_ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "sid", "iss", "aud", "iat", "exp", "jti"]},
    )


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)
