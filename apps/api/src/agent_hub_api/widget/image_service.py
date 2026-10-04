from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.core.identifiers import new_uuid_v7
from agent_hub_api.widget.image_storage import (
    VisitorImageStorage,
    VisitorImageStorageError,
)
from agent_hub_api.widget.image_validation import validate_and_sanitize_image
from agent_hub_api.widget.models import VisitorImageUpload
from agent_hub_api.widget.public_schemas import WidgetImageUploadResponse
from agent_hub_api.widget.visitor_service import WidgetVisitorService


class VisitorImageService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        storage: VisitorImageStorage,
    ) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage

    async def upload(
        self,
        *,
        token: str,
        origin: str,
        content: bytes,
        declared_content_type: str,
    ) -> WidgetImageUploadResponse:
        if self.settings.vision_model is None:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "IMAGE_INPUT_DISABLED",
                "Chatbot hiện chưa hỗ trợ nhận ảnh.",
            )
        async with self.session.begin():
            context = await WidgetVisitorService(
                self.session, self.settings, image_input_enabled=True
            ).resolve_context(token=token, origin=origin)
            image = validate_and_sanitize_image(
                content,
                declared_content_type=declared_content_type,
                max_bytes=self.settings.widget_image_max_bytes,
                max_pixels=self.settings.widget_image_max_pixels,
            )
            count = await self.session.scalar(
                select(func.count(VisitorImageUpload.id)).where(
                    VisitorImageUpload.workspace_id == context.workspace_id,
                    VisitorImageUpload.session_id == context.session_id,
                    VisitorImageUpload.status != "deleted",
                )
            )
            byte_total = await self.session.scalar(
                select(func.coalesce(func.sum(VisitorImageUpload.byte_size), 0)).where(
                    VisitorImageUpload.workspace_id == context.workspace_id,
                    VisitorImageUpload.session_id == context.session_id,
                    VisitorImageUpload.status != "deleted",
                )
            )
            if int(count or 0) >= self.settings.widget_image_session_max_uploads or (
                int(byte_total or 0) + len(image.content)
                > self.settings.widget_image_session_max_bytes
            ):
                raise ApiError(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "IMAGE_QUOTA_EXCEEDED",
                    "Phiên chat đã dùng hết giới hạn tải ảnh.",
                )
            public_id = new_uuid_v7()
            object_key = (
                f"workspaces/{context.workspace_id}/visitor-images/{context.session_id}/"
                f"{secrets.token_urlsafe(18)}.{image.extension}"
            )
            expires_at = datetime.now(UTC) + timedelta(
                minutes=self.settings.widget_image_unattached_minutes
            )
            upload = VisitorImageUpload(
                public_id=public_id,
                workspace_id=context.workspace_id,
                session_id=context.session_id,
                object_key=object_key,
                content_type=image.content_type,
                byte_size=len(image.content),
                width=image.width,
                height=image.height,
                sha256=hashlib.sha256(image.content).hexdigest(),
                status="uploading",
                expires_at=expires_at,
            )
            self.session.add(upload)
            await self.session.flush()
        try:
            await self.storage.upload(
                object_key=object_key,
                content=image.content,
                content_type=image.content_type,
            )
        except VisitorImageStorageError as exc:
            async with self.session.begin():
                stored = await self.session.get(VisitorImageUpload, upload.id)
                if stored is not None:
                    stored.status = "cleanup_pending"
                    stored.updated_at = datetime.now(UTC)
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                "Không thể lưu ảnh lúc này.",
            ) from exc
        async with self.session.begin():
            stored = await self.session.get(VisitorImageUpload, upload.id)
            if stored is None:
                raise RuntimeError("Visitor image metadata disappeared")
            stored.status = "available"
            stored.updated_at = datetime.now(UTC)
        return WidgetImageUploadResponse(
            attachment_id=public_id,
            content_type=cast(
                Literal["image/jpeg", "image/png", "image/webp"], image.content_type
            ),
            width=image.width,
            height=image.height,
            expires_at=expires_at,
        )

    async def delete(
        self,
        *,
        token: str,
        origin: str,
        attachment_id: UUID,
    ) -> None:
        async with self.session.begin():
            context = await WidgetVisitorService(
                self.session, self.settings, image_input_enabled=True
            ).resolve_context(token=token, origin=origin)
            upload = (
                await self.session.scalars(
                    select(VisitorImageUpload)
                    .where(
                        VisitorImageUpload.workspace_id == context.workspace_id,
                        VisitorImageUpload.session_id == context.session_id,
                        VisitorImageUpload.public_id == attachment_id,
                        VisitorImageUpload.status == "available",
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if upload is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy ảnh.",
                )
            upload.status = "cleanup_pending"
            object_key = upload.object_key
        if object_key is None:
            raise RuntimeError("Available visitor image has no storage object")
        try:
            await self.storage.delete(object_key=object_key)
        except VisitorImageStorageError as exc:
            raise ApiError(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "STORAGE_UNAVAILABLE",
                "Không thể xóa ảnh lúc này.",
            ) from exc
        async with self.session.begin():
            stored = await self.session.get(VisitorImageUpload, upload.id)
            if stored is not None:
                stored.status = "deleted"
                stored.object_key = None
                stored.updated_at = datetime.now(UTC)
