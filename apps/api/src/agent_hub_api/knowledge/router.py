from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, get_request_settings, require_csrf
from agent_hub_api.identity.models import User
from agent_hub_api.knowledge.schemas import (
    AgentKnowledgeBasesRequest,
    AgentKnowledgeBasesResponse,
    IngestionJobResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
    KnowledgeDocumentKind,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    ManualKnowledgeRequest,
)
from agent_hub_api.knowledge.service import KnowledgeService
from agent_hub_api.knowledge.storage import KnowledgeStorage, UnavailableKnowledgeStorage
from agent_hub_api.knowledge.upload import stage_knowledge_upload

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["knowledge"])


def get_knowledge_storage(request: Request) -> KnowledgeStorage:
    storage: KnowledgeStorage | None = getattr(request.app.state, "knowledge_storage", None)
    return storage or UnavailableKnowledgeStorage()


def service(
    session: AsyncSession, settings: Settings, storage: KnowledgeStorage
) -> KnowledgeService:
    return KnowledgeService(session, settings, storage)


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> KnowledgeBaseListResponse:
    return await service(session, settings, storage).list_bases(
        user, workspace_id, limit=limit, cursor=cursor
    )


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_knowledge_base(
    workspace_id: UUID,
    payload: KnowledgeBaseCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> KnowledgeBaseResponse:
    return await service(session, settings, storage).create_base(user, workspace_id, payload)


@router.patch(
    "/knowledge-bases/{base_id}",
    response_model=KnowledgeBaseResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_knowledge_base(
    workspace_id: UUID,
    base_id: int,
    payload: KnowledgeBaseUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> KnowledgeBaseResponse:
    return await service(session, settings, storage).update_base(
        user, workspace_id, base_id, payload
    )


@router.delete(
    "/knowledge-bases/{base_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def archive_knowledge_base(
    workspace_id: UUID,
    base_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> None:
    await service(session, settings, storage).archive_base(user, workspace_id, base_id)


@router.get(
    "/agents/{public_agent_id}/knowledge-bases",
    response_model=AgentKnowledgeBasesResponse,
)
async def get_agent_knowledge_bases(
    workspace_id: UUID,
    public_agent_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> AgentKnowledgeBasesResponse:
    return await service(session, settings, storage).get_agent_bases(
        user, workspace_id, public_agent_id
    )


@router.put(
    "/agents/{public_agent_id}/knowledge-bases",
    response_model=AgentKnowledgeBasesResponse,
    dependencies=[Depends(require_csrf)],
)
async def replace_agent_knowledge_bases(
    workspace_id: UUID,
    public_agent_id: UUID,
    payload: AgentKnowledgeBasesRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> AgentKnowledgeBasesResponse:
    return await service(session, settings, storage).replace_agent_bases(
        user, workspace_id, public_agent_id, payload
    )


@router.post(
    "/knowledge-bases/{base_id}/documents/text",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_manual_knowledge_document(
    workspace_id: UUID,
    base_id: int,
    payload: ManualKnowledgeRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> KnowledgeDocumentResponse:
    return await service(session, settings, storage).create_manual_document(
        user, workspace_id, base_id, payload, idempotency_key
    )


@router.post(
    "/knowledge-bases/{base_id}/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_knowledge_document(
    workspace_id: UUID,
    base_id: int,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=240)],
    kind: Annotated[KnowledgeDocumentKind, Form()] = "document",
) -> KnowledgeDocumentResponse:
    staged = await stage_knowledge_upload(file, max_bytes=settings.knowledge_document_max_bytes)
    try:
        return await service(session, settings, storage).create_file_document(
            user,
            workspace_id,
            base_id,
            title=title,
            kind=kind,
            idempotency_key=idempotency_key,
            staged=staged,
        )
    finally:
        staged.cleanup()


@router.get(
    "/knowledge-bases/{base_id}/documents",
    response_model=KnowledgeDocumentListResponse,
)
async def list_knowledge_documents(
    workspace_id: UUID,
    base_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> KnowledgeDocumentListResponse:
    return await service(session, settings, storage).list_documents(
        user, workspace_id, base_id, limit=limit, cursor=cursor
    )


@router.delete(
    "/knowledge-bases/{base_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_knowledge_document(
    workspace_id: UUID,
    base_id: int,
    document_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> None:
    await service(session, settings, storage).delete_document(
        user, workspace_id, base_id, document_id
    )


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    workspace_id: UUID,
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> IngestionJobResponse:
    return await service(session, settings, storage).get_job(user, workspace_id, job_id)


@router.post(
    "/ingestion-jobs/{job_id}/retry",
    response_model=IngestionJobResponse,
    dependencies=[Depends(require_csrf)],
)
async def retry_ingestion_job(
    workspace_id: UUID,
    job_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[KnowledgeStorage, Depends(get_knowledge_storage)],
) -> IngestionJobResponse:
    return await service(session, settings, storage).retry_job(user, workspace_id, job_id)
