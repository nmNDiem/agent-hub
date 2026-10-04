from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.leads.models import Lead
from agent_hub_api.leads.repository import LeadRepository, LeadRow
from agent_hub_api.leads.schemas import (
    LeadCaptureRequest,
    LeadCaptureResponse,
    LeadListResponse,
    LeadResponse,
    LeadStatus,
    contact_consent_version,
)
from agent_hub_api.widget.models import Conversation
from agent_hub_api.widget.visitor_service import WidgetVisitorService
from agent_hub_api.workspaces.service import WorkspaceService


def _request_hash(payload: LeadCaptureRequest) -> str:
    canonical = json.dumps(
        {
            "name": payload.name,
            "email": str(payload.email).casefold() if payload.email is not None else None,
            "phone": payload.phone,
            "consent_text_version": payload.consent_text_version,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _encode_cursor(created_at: datetime, item_id: int) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": item_id}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, int | None]:
    if cursor is None:
        return None, None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        item_id = int(payload["id"])
        if created_at.tzinfo is None or item_id < 1:
            raise ValueError
        return created_at, item_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Con trỏ phân trang không hợp lệ.",
        ) from exc


def _response(row: LeadRow) -> LeadResponse:
    lead, conversation_public_id, agent_public_id, agent_name = row
    return LeadResponse(
        id=lead.id,
        conversation_public_id=conversation_public_id,
        agent_public_id=agent_public_id,
        agent_name=agent_name,
        name=lead.name,
        email=lead.normalized_email,
        phone=lead.phone,
        consent_at=lead.consent_at,
        consent_text_version=lead.consent_text_version,
        followup_status=cast(LeadStatus, lead.followup_status),
        retention_until=lead.retention_until,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _csv_cell(value: object | None) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


class LeadService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = LeadRepository(session)

    async def capture(
        self,
        *,
        token: str,
        origin: str,
        conversation_public_id: UUID,
        idempotency_key: str,
        payload: LeadCaptureRequest,
    ) -> LeadCaptureResponse:
        if payload.consent_text_version != contact_consent_version(
            self.settings.lead_retention_days
        ):
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "CONSENT_VERSION_CHANGED",
                "Nội dung đồng ý đã thay đổi. Vui lòng xem lại và gửi lại.",
            )
        digest = _request_hash(payload)
        async with self.session.begin():
            context = await WidgetVisitorService(self.session, self.settings).resolve_context(
                token=token, origin=origin
            )
            conversation = (
                await self.session.scalars(
                    select(Conversation)
                    .where(
                        Conversation.workspace_id == context.workspace_id,
                        Conversation.session_id == context.session_id,
                        Conversation.public_id == conversation_public_id,
                        Conversation.status == "open",
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if conversation is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy cuộc trò chuyện.",
                )
            existing = await self.repository.by_session_key(context.session_id, idempotency_key)
            if existing is not None:
                if existing.request_hash != digest:
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "IDEMPOTENCY_CONFLICT",
                        "Khóa gửi liên hệ đã được dùng cho nội dung khác.",
                    )
                return LeadCaptureResponse(
                    followup_status=cast(LeadStatus, existing.followup_status),
                    retention_until=existing.retention_until,
                )
            existing = await self.repository.by_conversation(conversation.id)
            if existing is not None:
                if existing.request_hash == digest:
                    return LeadCaptureResponse(
                        followup_status=cast(LeadStatus, existing.followup_status),
                        retention_until=existing.retention_until,
                    )
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "LEAD_ALREADY_CAPTURED",
                    "Yêu cầu liên hệ đã được ghi nhận cho cuộc trò chuyện này.",
                )
            now = datetime.now(UTC)
            lead = Lead(
                workspace_id=context.workspace_id,
                conversation_id=conversation.id,
                session_id=context.session_id,
                agent_id=context.agent_id,
                name=payload.name,
                normalized_email=(
                    str(payload.email).casefold() if payload.email is not None else None
                ),
                phone=payload.phone,
                consent_at=now,
                consent_text_version=payload.consent_text_version,
                idempotency_key=idempotency_key,
                request_hash=digest,
                followup_status="new",
                retention_until=now + timedelta(days=self.settings.lead_retention_days),
            )
            self.session.add(lead)
            await self.session.flush()
        return LeadCaptureResponse(
            followup_status="new", retention_until=lead.retention_until
        )

    async def _authorize_admin(self, user: User, workspace_id: UUID) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền xem thông tin khách tiềm năng.",
            )

    async def list(
        self,
        user: User,
        workspace_id: UUID,
        *,
        limit: int,
        cursor: str | None,
        followup_status: LeadStatus | None,
    ) -> LeadListResponse:
        await self._authorize_admin(user, workspace_id)
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        rows = await self.repository.list(
            workspace_id,
            limit=limit + 1,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
            followup_status=followup_status,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_more and page:
            last = page[-1][0]
            next_cursor = _encode_cursor(last.created_at, last.id)
        return LeadListResponse(items=[_response(row) for row in page], next_cursor=next_cursor)

    async def update_status(
        self,
        user: User,
        workspace_id: UUID,
        lead_id: int,
        followup_status: LeadStatus,
    ) -> LeadResponse:
        async with self.session.begin():
            await self._authorize_admin(user, workspace_id)
            lead = await self.repository.get_for_update(workspace_id, lead_id)
            if lead is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy lead.")
            lead.followup_status = followup_status
            lead.updated_at = datetime.now(UTC)
        row = await self.repository.detail(workspace_id, lead.id)
        if row is None:
            raise RuntimeError("Updated lead could not be reloaded")
        return _response(row)

    async def export_csv(
        self,
        user: User,
        workspace_id: UUID,
        *,
        followup_status: LeadStatus | None,
    ) -> bytes:
        await self._authorize_admin(user, workspace_id)
        rows = await self.repository.list(
            workspace_id,
            limit=self.settings.lead_export_max_rows + 1,
            followup_status=followup_status,
        )
        if len(rows) > self.settings.lead_export_max_rows:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "LEAD_EXPORT_TOO_LARGE",
                "Có quá nhiều lead để xuất trong một tệp. Hãy lọc theo trạng thái.",
            )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "lead_id",
                "conversation_public_id",
                "chatbot",
                "name",
                "email",
                "phone",
                "followup_status",
                "consent_at",
                "consent_text_version",
                "retention_until",
            ]
        )
        for lead, conversation_public_id, _agent_public_id, agent_name in rows:
            writer.writerow(
                [
                    lead.id,
                    conversation_public_id,
                    _csv_cell(agent_name),
                    _csv_cell(lead.name),
                    _csv_cell(lead.normalized_email),
                    _csv_cell(lead.phone),
                    lead.followup_status,
                    lead.consent_at.isoformat(),
                    lead.consent_text_version,
                    lead.retention_until.isoformat(),
                ]
            )
        return ("\ufeff" + output.getvalue()).encode("utf-8")
