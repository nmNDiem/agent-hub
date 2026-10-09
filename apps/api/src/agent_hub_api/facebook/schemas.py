from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class FacebookConnectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_public_id: UUID
    page_access_token: SecretStr


class FacebookConnectionReauthorizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_access_token: SecretStr


class FacebookConnectionResponse(BaseModel):
    id: int
    provider: Literal["facebook"] = "facebook"
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
    agent_public_id: UUID
    agent_name: str
    latest_queue_state: (
        Literal[
            "queued",
            "running",
            "completed",
            "failed_retryable",
            "failed_terminal",
            "suppressed",
        ]
        | None
    ) = None
    latest_delivery_state: (
        Literal[
            "queued",
            "sending",
            "accepted",
            "delivered",
            "failed_retryable",
            "failed_terminal",
        ]
        | None
    ) = None
    latest_safe_error_code: str | None = None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FacebookConnectionListResponse(BaseModel):
    items: list[FacebookConnectionResponse] = Field(default_factory=list)
