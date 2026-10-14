from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ZaloOAuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_public_id: UUID
    reauthorize_connection_id: int | None = Field(default=None, gt=0)


class ZaloOAuthStartResponse(BaseModel):
    authorization_url: str
    expires_at: datetime


class ZaloWebhookSecretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webhook_secret: SecretStr


class ZaloConnectionResponse(BaseModel):
    id: int
    provider: Literal["zalo"] = "zalo"
    display_name: str
    external_account_id: str
    lifecycle_state: Literal["active", "revoked"]
    health_state: Literal[
        "unknown",
        "healthy",
        "permission_expired",
        "reauth_required",
        "webhook_subscription_failure",
        "delivery_unknown",
    ]
    webhook_configured: bool
    agent_public_id: UUID
    agent_name: str
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ZaloConnectionListResponse(BaseModel):
    items: list[ZaloConnectionResponse] = Field(default_factory=list)
