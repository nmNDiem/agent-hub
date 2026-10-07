from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class FacebookConnectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_public_id: UUID
    page_access_token: SecretStr


class FacebookConnectionResponse(BaseModel):
    id: int
    provider: Literal["facebook"] = "facebook"
    display_name: str
    external_account_id: str
    lifecycle_state: Literal["active", "revoked"]
    health_state: Literal["unknown", "healthy", "degraded", "error"]
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FacebookConnectionListResponse(BaseModel):
    items: list[FacebookConnectionResponse] = Field(default_factory=list)
