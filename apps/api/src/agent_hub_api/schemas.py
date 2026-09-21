import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(TokenRequest):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    email_verified: bool


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


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str
    access_expires_at: datetime


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


class MessageResponse(BaseModel):
    message: str


def validate_password_strength(value: str) -> str:
    if not any(character.isalpha() for character in value) or not any(
        character.isdigit() for character in value
    ):
        raise ValueError("Password must contain at least one letter and one number")
    return value
