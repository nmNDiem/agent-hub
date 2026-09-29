from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.models import User
from agent_hub_api.knowledge.models import (
    IngestionJob,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeChunkEmbedding,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
    MediaAsset,
)
from agent_hub_api.knowledge.repository import KnowledgeRepository
from agent_hub_api.knowledge.schemas import (
    AgentKnowledgeBasesRequest,
    AgentKnowledgeBasesResponse,
    IngestionJobResponse,
    IngestionStatus,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseKind,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
    KnowledgeDocumentKind,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    ManualKnowledgeRequest,
)
from agent_hub_api.knowledge.storage import KnowledgeStorage, KnowledgeStorageError
from agent_hub_api.knowledge.upload import StagedKnowledgeUpload
from agent_hub_api.workspaces.models import Workspace
from agent_hub_api.workspaces.service import WorkspaceService

ACTIVE_JOB_STATUSES = {
    "uploading",
    "awaiting_profile",
    "queued",
    "processing",
    "retry_scheduled",
}


def encode_id_cursor(item_id: int) -> str:
    return base64.urlsafe_b64encode(str(item_id).encode()).decode().rstrip("=")


def decode_id_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        item_id = int(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Cursor không hợp lệ.",
        ) from exc
    if item_id < 1:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_CURSOR",
            "Cursor không hợp lệ.",
        )
    return item_id


class KnowledgeService:
    def __init__(
        self, session: AsyncSession, settings: Settings, storage: KnowledgeStorage
    ) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage
        self.repository = KnowledgeRepository(session)

    async def _authorize(self, user: User, workspace_id: UUID, *, write: bool = False) -> None:
        _, role = await WorkspaceService(self.session).get_for_user(user.id, workspace_id)
        if write and role not in {"owner", "admin"}:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "Bạn không có quyền thay đổi nguồn kiến thức.",
            )

    async def _base(self, workspace_id: UUID, base_id: int) -> KnowledgeBase:
        knowledge_base = await self.repository.get_base(workspace_id, base_id)
        if knowledge_base is None:
            raise ApiError(
                status.HTTP_404_NOT_FOUND,
                "NOT_FOUND",
                "Không tìm thấy kho kiến thức.",
            )
        return knowledge_base

    @staticmethod
    def _base_response(base: KnowledgeBase, document_count: int) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=base.id,
            name=base.name,
            kind=cast(KnowledgeBaseKind, base.kind),
            status=cast(Literal["active", "archived"], base.status),
            active_embedding_profile_id=base.active_embedding_profile_id,
            document_count=document_count,
            created_at=base.created_at,
            updated_at=base.updated_at,
        )

    @staticmethod
    def _job_response(job: IngestionJob) -> IngestionJobResponse:
        return IngestionJobResponse(
            id=job.id,
            document_id=job.document_id,
            document_version_id=job.document_version_id,
            target_generation_id=job.target_generation_id,
            status=cast(IngestionStatus, job.status),
            attempts=job.attempts,
            last_error_code=job.last_error_code,
            retryable=job.retryable,
            scheduled_at=job.scheduled_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )

    @classmethod
    def _document_response(
        cls,
        document: KnowledgeDocument,
        version: KnowledgeDocumentVersion,
        job: IngestionJob,
        active_generation_id: int | None,
    ) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            title=document.title,
            kind=cast(KnowledgeDocumentKind, document.kind),
            status=cast(Literal["active", "deleted"], document.status),
            source_kind=cast(Literal["manual", "file"], version.source_kind),
            version_no=version.version_no,
            mime_type=version.mime_type,
            byte_size=version.byte_size,
            active_generation_id=active_generation_id,
            ingestion_job=cls._job_response(job),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list_bases(
        self, user: User, workspace_id: UUID, *, limit: int, cursor: str | None
    ) -> KnowledgeBaseListResponse:
        await self._authorize(user, workspace_id)
        bases, counts, has_more = await self.repository.list_bases(
            workspace_id, limit=limit, cursor_id=decode_id_cursor(cursor)
        )
        return KnowledgeBaseListResponse(
            items=[self._base_response(item, counts.get(item.id, 0)) for item in bases],
            next_cursor=encode_id_cursor(bases[-1].id) if has_more and bases else None,
        )

    async def create_base(
        self, user: User, workspace_id: UUID, payload: KnowledgeBaseCreateRequest
    ) -> KnowledgeBaseResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            knowledge_base = KnowledgeBase(
                workspace_id=workspace_id,
                name=payload.name,
                kind=payload.kind,
            )
            self.session.add(knowledge_base)
            await self.session.flush()
        return self._base_response(knowledge_base, 0)

    async def update_base(
        self,
        user: User,
        workspace_id: UUID,
        base_id: int,
        payload: KnowledgeBaseUpdateRequest,
    ) -> KnowledgeBaseResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            knowledge_base = await self._base(workspace_id, base_id)
            if knowledge_base.status != "active":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "KNOWLEDGE_BASE_ARCHIVED",
                    "Kho đã lưu trữ.",
                )
            for field in payload.model_fields_set:
                value = getattr(payload, field)
                if value is None:
                    raise ApiError(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "VALIDATION_ERROR",
                        f"{field} cannot be null",
                    )
                setattr(knowledge_base, field, value)
            knowledge_base.updated_at = datetime.now(UTC)
        count = int(
            await self.session.scalar(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.workspace_id == workspace_id,
                    KnowledgeDocument.knowledge_base_id == base_id,
                    KnowledgeDocument.status == "active",
                )
            )
            or 0
        )
        return self._base_response(knowledge_base, count)

    async def archive_base(self, user: User, workspace_id: UUID, base_id: int) -> None:
        now = datetime.now(UTC)
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            knowledge_base = await self._base(workspace_id, base_id)
            if knowledge_base.status == "archived":
                return
            knowledge_base.status = "archived"
            knowledge_base.archived_at = now
            knowledge_base.updated_at = now
            document_ids = select(KnowledgeDocument.id).where(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.knowledge_base_id == base_id,
            )
            await self.session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.document_id.in_(document_ids),
                    IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
                )
                .values(
                    status="cancelled",
                    lease_token=None,
                    lease_version=IngestionJob.lease_version + 1,
                    completed_at=now,
                    updated_at=now,
                    last_error_code="KNOWLEDGE_BASE_ARCHIVED",
                    retryable=False,
                )
            )

    async def replace_agent_bases(
        self,
        user: User,
        workspace_id: UUID,
        public_agent_id: UUID,
        payload: AgentKnowledgeBasesRequest,
    ) -> AgentKnowledgeBasesResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            agent = await self.repository.get_agent(workspace_id, public_agent_id)
            if agent is None:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy agent.")
            found = set(
                await self.session.scalars(
                    select(KnowledgeBase.id).where(
                        KnowledgeBase.workspace_id == workspace_id,
                        KnowledgeBase.id.in_(payload.knowledge_base_ids),
                        KnowledgeBase.status == "active",
                    )
                )
            )
            if found != set(payload.knowledge_base_ids):
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy kho kiến thức.",
                )
            await self.repository.replace_agent_bases(
                workspace_id=workspace_id,
                agent_id=agent.id,
                base_ids=payload.knowledge_base_ids,
            )
        return AgentKnowledgeBasesResponse(
            public_agent_id=public_agent_id,
            knowledge_base_ids=payload.knowledge_base_ids,
        )

    async def get_agent_bases(
        self, user: User, workspace_id: UUID, public_agent_id: UUID
    ) -> AgentKnowledgeBasesResponse:
        await self._authorize(user, workspace_id)
        agent = await self.repository.get_agent(workspace_id, public_agent_id)
        if agent is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy agent.")
        return AgentKnowledgeBasesResponse(
            public_agent_id=public_agent_id,
            knowledge_base_ids=await self.repository.agent_base_ids(workspace_id, agent.id),
        )

    def _pipeline_hash(self, profile_id: int) -> str:
        payload = json.dumps(
            {
                "profile_id": profile_id,
                "chunker_version": "char-paragraph-v1",
                "chunk_size": self.settings.knowledge_chunk_size,
                "chunk_overlap": self.settings.knowledge_chunk_overlap,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    async def _generation_for(
        self,
        knowledge_base: KnowledgeBase,
        document: KnowledgeDocument,
        version: KnowledgeDocumentVersion,
    ) -> KnowledgeGeneration | None:
        if knowledge_base.active_embedding_profile_id is None:
            return None
        generation_no = int(
            await self.session.scalar(
                select(func.max(KnowledgeGeneration.generation_no)).where(
                    KnowledgeGeneration.document_id == document.id
                )
            )
            or 0
        ) + 1
        generation = KnowledgeGeneration(
            workspace_id=document.workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            embedding_profile_id=knowledge_base.active_embedding_profile_id,
            generation_no=generation_no,
            chunker_version="char-paragraph-v1",
            chunk_size=self.settings.knowledge_chunk_size,
            chunk_overlap=self.settings.knowledge_chunk_overlap,
            pipeline_config_hash=self._pipeline_hash(knowledge_base.active_embedding_profile_id),
        )
        self.session.add(generation)
        await self.session.flush()
        return generation

    async def _new_job(
        self,
        knowledge_base: KnowledgeBase,
        document: KnowledgeDocument,
        version: KnowledgeDocumentVersion,
        *,
        idempotency_key: str,
        request_sha256: str,
        status_override: str | None = None,
    ) -> IngestionJob:
        generation = None
        if status_override is None:
            generation = await self._generation_for(knowledge_base, document, version)
        job = IngestionJob(
            workspace_id=document.workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            target_generation_id=generation.id if generation is not None else None,
            status=status_override or ("queued" if generation is not None else "awaiting_profile"),
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def _existing_document_response(
        self, workspace_id: UUID, job: IngestionJob, request_sha256: str
    ) -> KnowledgeDocumentResponse:
        if job.request_sha256 != request_sha256:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency-Key đã được dùng cho nội dung khác.",
            )
        bundle = await self.repository.latest_document_bundle(workspace_id, job.document_id)
        if bundle is None:
            raise RuntimeError("Idempotency record references a missing document")
        return self._document_response(*bundle)

    async def create_manual_document(
        self,
        user: User,
        workspace_id: UUID,
        base_id: int,
        payload: ManualKnowledgeRequest,
        idempotency_key: str,
    ) -> KnowledgeDocumentResponse:
        if len(payload.content) > self.settings.knowledge_manual_max_chars:
            raise ApiError(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "KNOWLEDGE_TEXT_TOO_LARGE",
                "Nội dung kiến thức vượt quá giới hạn cho phép.",
            )
        content = payload.content.encode("utf-8")
        request_sha = hashlib.sha256(
            json.dumps(
                {
                    "base_id": base_id,
                    "title": payload.title,
                    "kind": payload.kind,
                    "content_sha256": hashlib.sha256(content).hexdigest(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            existing = await self.repository.job_by_idempotency(workspace_id, idempotency_key)
            if existing is not None:
                return await self._existing_document_response(workspace_id, existing, request_sha)
            knowledge_base = await self._base(workspace_id, base_id)
            if knowledge_base.status != "active":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "KNOWLEDGE_BASE_ARCHIVED",
                    "Kho đã lưu trữ.",
                )
            await self._enforce_workspace_limits(workspace_id, byte_size=len(content))
            document = KnowledgeDocument(
                workspace_id=workspace_id,
                knowledge_base_id=base_id,
                title=payload.title,
                kind=payload.kind,
            )
            self.session.add(document)
            await self.session.flush()
            version = KnowledgeDocumentVersion(
                workspace_id=workspace_id,
                document_id=document.id,
                version_no=1,
                source_kind="manual",
                source_text=payload.content,
                content_sha256=hashlib.sha256(content).hexdigest(),
                mime_type="text/plain",
                byte_size=len(content),
                created_by_user_id=user.id,
            )
            self.session.add(version)
            await self.session.flush()
            job = await self._new_job(
                knowledge_base,
                document,
                version,
                idempotency_key=idempotency_key,
                request_sha256=request_sha,
            )
        return self._document_response(document, version, job, None)

    async def _enforce_workspace_limits(self, workspace_id: UUID, *, byte_size: int) -> None:
        workspace = await self.session.scalar(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        if workspace is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy workspace.")
        document_count = int(
            await self.session.scalar(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.workspace_id == workspace_id,
                    KnowledgeDocument.status == "active",
                )
            )
            or 0
        )
        if document_count >= self.settings.knowledge_workspace_max_documents:
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "KNOWLEDGE_DOCUMENT_QUOTA",
                "Đã đạt giới hạn tài liệu.",
            )
        stored_bytes = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(MediaAsset.byte_size), 0)).where(
                    MediaAsset.workspace_id == workspace_id,
                    MediaAsset.status.in_({"reserved", "available"}),
                )
            )
            or 0
        )
        if stored_bytes + byte_size > self.settings.knowledge_workspace_storage_bytes:
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "KNOWLEDGE_STORAGE_QUOTA",
                "Đã đạt giới hạn lưu trữ.",
            )
        since = datetime.now(UTC) - timedelta(
            minutes=self.settings.knowledge_upload_window_minutes
        )
        if (
            await self.repository.recent_job_count(workspace_id, since)
            >= self.settings.knowledge_uploads_per_window
        ):
            raise ApiError(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "KNOWLEDGE_UPLOAD_RATE_LIMIT",
                "Vui lòng thử lại sau.",
            )

    def _file_request_hash(
        self, base_id: int, title: str, kind: str, staged: StagedKnowledgeUpload
    ) -> str:
        canonical = json.dumps(
            {
                "base_id": base_id,
                "title": title,
                "kind": kind,
                "content_sha256": staged.sha256,
                "mime_type": staged.mime_type,
                "byte_size": staged.byte_size,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def create_file_document(
        self,
        user: User,
        workspace_id: UUID,
        base_id: int,
        *,
        title: str,
        kind: KnowledgeDocumentKind,
        idempotency_key: str,
        staged: StagedKnowledgeUpload,
    ) -> KnowledgeDocumentResponse:
        request_sha = self._file_request_hash(base_id, title, kind, staged)
        asset: MediaAsset
        document: KnowledgeDocument
        version: KnowledgeDocumentVersion
        job: IngestionJob
        should_upload = True
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            existing = await self.repository.job_by_idempotency(workspace_id, idempotency_key)
            if existing is not None:
                response = await self._existing_document_response(
                    workspace_id, existing, request_sha
                )
                version = await self.repository.version(workspace_id, existing.document_version_id)
                if version.media_asset_id is None:
                    return response
                asset = await self.repository.asset(workspace_id, version.media_asset_id)
                existing_document = await self.repository.get_document(
                    workspace_id, existing.document_id
                )
                if existing_document is None:
                    raise RuntimeError("Idempotency record references a missing document")
                document = existing_document
                job = existing
                should_upload = asset.status in {"reserved", "failed"}
                if not should_upload:
                    return response
                asset.status = "reserved"
                job.status = "uploading"
                job.last_error_code = None
                job.retryable = False
            else:
                knowledge_base = await self._base(workspace_id, base_id)
                if knowledge_base.status != "active":
                    raise ApiError(
                        status.HTTP_409_CONFLICT,
                        "KNOWLEDGE_BASE_ARCHIVED",
                        "Kho đã lưu trữ.",
                    )
                await self._enforce_workspace_limits(workspace_id, byte_size=staged.byte_size)
                suffix = ".pdf" if staged.mime_type == "application/pdf" else ".txt"
                object_key = (
                    f"workspaces/{workspace_id}/knowledge/"
                    f"{secrets.token_urlsafe(24)}{suffix}"
                )
                asset = MediaAsset(
                    workspace_id=workspace_id,
                    bucket=self.settings.storage_private_bucket,
                    object_key=object_key,
                    original_filename=staged.filename,
                    mime_type=staged.mime_type,
                    byte_size=staged.byte_size,
                    sha256=staged.sha256,
                )
                self.session.add(asset)
                await self.session.flush()
                document = KnowledgeDocument(
                    workspace_id=workspace_id,
                    knowledge_base_id=base_id,
                    title=title.strip(),
                    kind=kind,
                )
                self.session.add(document)
                await self.session.flush()
                version = KnowledgeDocumentVersion(
                    workspace_id=workspace_id,
                    document_id=document.id,
                    version_no=1,
                    source_kind="file",
                    media_asset_id=asset.id,
                    content_sha256=staged.sha256,
                    mime_type=staged.mime_type,
                    byte_size=staged.byte_size,
                    created_by_user_id=user.id,
                )
                self.session.add(version)
                await self.session.flush()
                job = await self._new_job(
                    knowledge_base,
                    document,
                    version,
                    idempotency_key=idempotency_key,
                    request_sha256=request_sha,
                    status_override="uploading",
                )
        if should_upload:
            try:
                await self.storage.upload_file(
                    object_key=asset.object_key,
                    source=staged.path,
                    content_type=staged.mime_type,
                )
            except KnowledgeStorageError as exc:
                async with self.session.begin():
                    stored_asset = await self.repository.asset(workspace_id, asset.id)
                    stored_job = await self.repository.job(workspace_id, job.id)
                    stored_asset.status = "failed"
                    if stored_job is not None and stored_job.status == "uploading":
                        stored_job.status = "failed"
                        stored_job.last_error_code = "STORAGE_UPLOAD_FAILED"
                        stored_job.retryable = False
                        stored_job.completed_at = datetime.now(UTC)
                raise ApiError(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "KNOWLEDGE_STORAGE_UNAVAILABLE",
                    "Chưa thể lưu tệp kiến thức. Vui lòng thử lại.",
                ) from exc
        async with self.session.begin():
            stored_asset = await self.repository.asset(workspace_id, asset.id)
            stored_job = await self.repository.job(workspace_id, job.id)
            knowledge_base = await self._base(workspace_id, base_id)
            if stored_job is None or stored_job.status != "uploading":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "INGESTION_STATE_CONFLICT",
                    "Trạng thái ingest đã thay đổi.",
                )
            stored_asset.status = "available"
            generation = await self._generation_for(knowledge_base, document, version)
            stored_job.target_generation_id = generation.id if generation is not None else None
            stored_job.status = "queued" if generation is not None else "awaiting_profile"
            stored_job.completed_at = None
            stored_job.updated_at = datetime.now(UTC)
            job = stored_job
        return self._document_response(document, version, job, None)

    async def list_documents(
        self,
        user: User,
        workspace_id: UUID,
        base_id: int,
        *,
        limit: int,
        cursor: str | None,
    ) -> KnowledgeDocumentListResponse:
        await self._authorize(user, workspace_id)
        await self._base(workspace_id, base_id)
        documents, versions, jobs, active, has_more = await self.repository.list_documents(
            workspace_id,
            base_id,
            limit=limit,
            cursor_id=decode_id_cursor(cursor),
        )
        return KnowledgeDocumentListResponse(
            items=[
                self._document_response(
                    document,
                    versions[document.id],
                    jobs[document.id],
                    active.get(document.id),
                )
                for document in documents
            ],
            next_cursor=encode_id_cursor(documents[-1].id) if has_more and documents else None,
        )

    async def delete_document(
        self, user: User, workspace_id: UUID, base_id: int, document_id: int
    ) -> None:
        now = datetime.now(UTC)
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            await self._base(workspace_id, base_id)
            document = await self.repository.get_document(workspace_id, document_id)
            if document is None or document.knowledge_base_id != base_id:
                raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy tài liệu.")
            if document.status == "deleted":
                return
            document.status = "deleted"
            document.deleted_at = now
            document.updated_at = now
            await self.session.execute(
                delete(KnowledgeDocumentActiveGeneration).where(
                    KnowledgeDocumentActiveGeneration.workspace_id == workspace_id,
                    KnowledgeDocumentActiveGeneration.document_id == document_id,
                )
            )
            await self.session.execute(
                update(KnowledgeGeneration)
                .where(
                    KnowledgeGeneration.workspace_id == workspace_id,
                    KnowledgeGeneration.document_id == document_id,
                )
                .values(status="revoked")
            )
            chunk_ids = (
                select(KnowledgeChunk.id)
                .join(
                    KnowledgeGeneration,
                    (KnowledgeGeneration.workspace_id == KnowledgeChunk.workspace_id)
                    & (KnowledgeGeneration.id == KnowledgeChunk.generation_id),
                )
                .where(
                    KnowledgeChunk.workspace_id == workspace_id,
                    KnowledgeGeneration.document_id == document_id,
                )
            )
            await self.session.execute(
                update(KnowledgeChunkEmbedding)
                .where(
                    KnowledgeChunkEmbedding.workspace_id == workspace_id,
                    KnowledgeChunkEmbedding.chunk_id.in_(chunk_ids),
                )
                .values(status="deleting")
            )
            await self.session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.document_id == document_id,
                    IngestionJob.status.in_(ACTIVE_JOB_STATUSES),
                )
                .values(
                    status="cancelled",
                    lease_token=None,
                    lease_version=IngestionJob.lease_version + 1,
                    completed_at=now,
                    last_error_code="DOCUMENT_DELETED",
                    retryable=False,
                )
            )
            asset_ids = select(KnowledgeDocumentVersion.media_asset_id).where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.document_id == document_id,
                KnowledgeDocumentVersion.media_asset_id.is_not(None),
            )
            await self.session.execute(
                update(MediaAsset)
                .where(
                    MediaAsset.workspace_id == workspace_id,
                    MediaAsset.id.in_(asset_ids),
                    MediaAsset.status.not_in({"deleted", "delete_pending"}),
                )
                .values(status="delete_pending", updated_at=now)
            )

    async def get_job(
        self, user: User, workspace_id: UUID, job_id: int
    ) -> IngestionJobResponse:
        await self._authorize(user, workspace_id)
        job = await self.repository.job(workspace_id, job_id)
        if job is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Không tìm thấy ingestion job.")
        return self._job_response(job)

    async def retry_job(
        self, user: User, workspace_id: UUID, job_id: int
    ) -> IngestionJobResponse:
        async with self.session.begin():
            await self._authorize(user, workspace_id, write=True)
            job = await self.repository.job(workspace_id, job_id)
            if job is None:
                raise ApiError(
                    status.HTTP_404_NOT_FOUND,
                    "NOT_FOUND",
                    "Không tìm thấy ingestion job.",
                )
            if job.status != "failed" or not job.retryable:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "INGESTION_NOT_RETRYABLE",
                    "Lỗi này không thể retry; hãy tạo phiên bản nguồn mới.",
                )
            if job.attempts >= self.settings.knowledge_job_max_attempts:
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "INGESTION_ATTEMPTS_EXHAUSTED",
                    "Ingestion job đã hết số lần thử.",
                )
            document = await self.repository.get_document(workspace_id, job.document_id)
            if document is None or document.status != "active":
                raise ApiError(
                    status.HTTP_409_CONFLICT,
                    "DOCUMENT_NOT_ACTIVE",
                    "Tài liệu không còn hoạt động.",
                )
            job.status = "queued" if job.target_generation_id is not None else "awaiting_profile"
            job.scheduled_at = datetime.now(UTC)
            job.last_error_code = None
            job.retryable = False
            job.completed_at = None
            job.updated_at = datetime.now(UTC)
        return self._job_response(job)
