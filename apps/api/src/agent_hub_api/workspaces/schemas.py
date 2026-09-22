import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from agent_hub_api.identity.schemas import UserResponse

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceResponse(BaseModel):
    id: UUID
    slug: str
    display_name: str
    timezone: str
    role: Literal["owner", "admin", "member"]
    created_at: datetime


class MeResponse(BaseModel):
    user: UserResponse
    workspaces: list[WorkspaceResponse]


class CreateWorkspaceRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=63)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=1, max_length=64)

    @field_validator("display_name", "slug", "timezone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not SLUG_PATTERN.fullmatch(normalized):
            raise ValueError("Slug must contain lowercase letters, numbers and single hyphens")
        return normalized


class UpdateWorkspaceRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("display_name", "timezone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()
