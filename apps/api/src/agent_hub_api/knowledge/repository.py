from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import Agent
from agent_hub_api.knowledge.models import (
    AgentKnowledgeBase,
    IngestionJob,
    KnowledgeBase,
    KnowledgeDocument,
    KnowledgeDocumentActiveGeneration,
    KnowledgeDocumentVersion,
    KnowledgeGeneration,
    KnowledgeRecoveryEvent,
    MediaAsset,
)


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_bases(
        self, workspace_id: UUID, *, limit: int, cursor_id: int | None
    ) -> tuple[list[KnowledgeBase], dict[int, int], bool]:
        query = select(KnowledgeBase).where(KnowledgeBase.workspace_id == workspace_id)
        if cursor_id is not None:
            query = query.where(KnowledgeBase.id < cursor_id)
        rows = list(
            (
                await self.session.scalars(
                    query.order_by(KnowledgeBase.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        counts: dict[int, int] = {}
        if rows:
            count_rows = (
                await self.session.execute(
                    select(KnowledgeDocument.knowledge_base_id, func.count(KnowledgeDocument.id))
                    .where(
                        KnowledgeDocument.workspace_id == workspace_id,
                        KnowledgeDocument.knowledge_base_id.in_([item.id for item in rows]),
                        KnowledgeDocument.status == "active",
                    )
                    .group_by(KnowledgeDocument.knowledge_base_id)
                )
            ).all()
            counts = {base_id: count for base_id, count in count_rows}
        return rows, counts, has_more

    async def get_base(self, workspace_id: UUID, base_id: int) -> KnowledgeBase | None:
        return cast(
            KnowledgeBase | None,
            await self.session.scalar(
                select(KnowledgeBase).where(
                    KnowledgeBase.workspace_id == workspace_id,
                    KnowledgeBase.id == base_id,
                )
            ),
        )

    async def get_agent(self, workspace_id: UUID, public_id: UUID) -> Agent | None:
        return cast(
            Agent | None,
            await self.session.scalar(
                select(Agent).where(
                    Agent.workspace_id == workspace_id,
                    Agent.public_id == public_id,
                    Agent.archived_at.is_(None),
                )
            ),
        )

    async def replace_agent_bases(
        self, *, workspace_id: UUID, agent_id: int, base_ids: list[int]
    ) -> None:
        await self.session.execute(
            delete(AgentKnowledgeBase).where(
                AgentKnowledgeBase.workspace_id == workspace_id,
                AgentKnowledgeBase.agent_id == agent_id,
            )
        )
        self.session.add_all(
            [
                AgentKnowledgeBase(
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    knowledge_base_id=base_id,
                )
                for base_id in base_ids
            ]
        )
        await self.session.flush()

    async def agent_base_ids(self, workspace_id: UUID, agent_id: int) -> list[int]:
        return list(
            await self.session.scalars(
                select(AgentKnowledgeBase.knowledge_base_id)
                .where(
                    AgentKnowledgeBase.workspace_id == workspace_id,
                    AgentKnowledgeBase.agent_id == agent_id,
                )
                .order_by(AgentKnowledgeBase.knowledge_base_id)
            )
        )

    async def get_document(
        self, workspace_id: UUID, document_id: int
    ) -> KnowledgeDocument | None:
        return cast(
            KnowledgeDocument | None,
            await self.session.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.workspace_id == workspace_id,
                    KnowledgeDocument.id == document_id,
                )
            ),
        )

    async def list_documents(
        self,
        workspace_id: UUID,
        base_id: int,
        *,
        limit: int,
        cursor_id: int | None,
    ) -> tuple[
        list[KnowledgeDocument],
        dict[int, KnowledgeDocumentVersion],
        dict[int, IngestionJob],
        dict[int, tuple[int, int]],
        bool,
    ]:
        query = select(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace_id,
            KnowledgeDocument.knowledge_base_id == base_id,
        )
        if cursor_id is not None:
            query = query.where(KnowledgeDocument.id < cursor_id)
        documents = list(
            (
                await self.session.scalars(
                    query.order_by(KnowledgeDocument.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(documents) > limit
        documents = documents[:limit]
        if not documents:
            return [], {}, {}, {}, has_more
        document_ids = [document.id for document in documents]
        versions = list(
            (
                await self.session.scalars(
                    select(KnowledgeDocumentVersion)
                    .where(
                        KnowledgeDocumentVersion.workspace_id == workspace_id,
                        KnowledgeDocumentVersion.document_id.in_(document_ids),
                    )
                    .order_by(
                        KnowledgeDocumentVersion.document_id,
                        KnowledgeDocumentVersion.version_no.desc(),
                    )
                )
            ).all()
        )
        jobs = list(
            (
                await self.session.scalars(
                    select(IngestionJob)
                    .where(
                        IngestionJob.workspace_id == workspace_id,
                        IngestionJob.document_id.in_(document_ids),
                    )
                    .order_by(IngestionJob.document_id, IngestionJob.id.desc())
                )
            ).all()
        )
        active_rows = (
            await self.session.execute(
                select(
                    KnowledgeDocumentActiveGeneration.document_id,
                    KnowledgeDocumentActiveGeneration.generation_id,
                    KnowledgeDocumentVersion.version_no,
                )
                .join(
                    KnowledgeGeneration,
                    KnowledgeGeneration.id == KnowledgeDocumentActiveGeneration.generation_id,
                )
                .join(
                    KnowledgeDocumentVersion,
                    KnowledgeDocumentVersion.id == KnowledgeGeneration.document_version_id,
                )
                .where(
                    KnowledgeDocumentActiveGeneration.workspace_id == workspace_id,
                    KnowledgeDocumentActiveGeneration.document_id.in_(document_ids),
                )
            )
        ).all()
        latest_versions: dict[int, KnowledgeDocumentVersion] = {}
        latest_jobs: dict[int, IngestionJob] = {}
        for version in versions:
            latest_versions.setdefault(version.document_id, version)
        for job in jobs:
            latest_jobs.setdefault(job.document_id, job)
        return (
            documents,
            latest_versions,
            latest_jobs,
            {
                document_id: (generation_id, version_no)
                for document_id, generation_id, version_no in active_rows
            },
            has_more,
        )

    async def list_versions(
        self,
        workspace_id: UUID,
        document_id: int,
        *,
        limit: int,
        cursor_id: int | None,
    ) -> tuple[
        list[KnowledgeDocumentVersion],
        dict[int, KnowledgeGeneration],
        dict[int, IngestionJob],
        int | None,
        int | None,
        bool,
    ]:
        query = select(KnowledgeDocumentVersion).where(
            KnowledgeDocumentVersion.workspace_id == workspace_id,
            KnowledgeDocumentVersion.document_id == document_id,
        )
        if cursor_id is not None:
            query = query.where(KnowledgeDocumentVersion.id < cursor_id)
        versions = list(
            (
                await self.session.scalars(
                    query.order_by(KnowledgeDocumentVersion.id.desc()).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(versions) > limit
        versions = versions[:limit]
        if not versions:
            active_generation_id = await self.active_generation_id(workspace_id, document_id)
            active_version_id = (
                await self.session.scalar(
                    select(KnowledgeGeneration.document_version_id).where(
                        KnowledgeGeneration.workspace_id == workspace_id,
                        KnowledgeGeneration.id == active_generation_id,
                    )
                )
                if active_generation_id is not None
                else None
            )
            return [], {}, {}, active_generation_id, active_version_id, has_more
        version_ids = [version.id for version in versions]
        generations = list(
            (
                await self.session.scalars(
                    select(KnowledgeGeneration)
                    .where(
                        KnowledgeGeneration.workspace_id == workspace_id,
                        KnowledgeGeneration.document_version_id.in_(version_ids),
                    )
                    .order_by(
                        KnowledgeGeneration.document_version_id,
                        KnowledgeGeneration.generation_no.desc(),
                    )
                )
            ).all()
        )
        jobs = list(
            (
                await self.session.scalars(
                    select(IngestionJob)
                    .where(
                        IngestionJob.workspace_id == workspace_id,
                        IngestionJob.document_version_id.in_(version_ids),
                    )
                    .order_by(IngestionJob.document_version_id, IngestionJob.id.desc())
                )
            ).all()
        )
        latest_generations: dict[int, KnowledgeGeneration] = {}
        latest_jobs: dict[int, IngestionJob] = {}
        for generation in generations:
            latest_generations.setdefault(generation.document_version_id, generation)
        for job in jobs:
            latest_jobs.setdefault(job.document_version_id, job)
        active_generation_id = await self.active_generation_id(workspace_id, document_id)
        active_version_id = (
            await self.session.scalar(
                select(KnowledgeGeneration.document_version_id).where(
                    KnowledgeGeneration.workspace_id == workspace_id,
                    KnowledgeGeneration.id == active_generation_id,
                )
            )
            if active_generation_id is not None
            else None
        )
        return (
            versions,
            latest_generations,
            latest_jobs,
            active_generation_id,
            cast(int | None, active_version_id),
            has_more,
        )

    async def job(self, workspace_id: UUID, job_id: int) -> IngestionJob | None:
        return cast(
            IngestionJob | None,
            await self.session.scalar(
                select(IngestionJob).where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.id == job_id,
                )
            ),
        )

    async def job_by_idempotency(
        self, workspace_id: UUID, idempotency_key: str
    ) -> IngestionJob | None:
        return cast(
            IngestionJob | None,
            await self.session.scalar(
                select(IngestionJob).where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.idempotency_key == idempotency_key,
                )
            ),
        )

    async def recovery_by_idempotency(
        self, workspace_id: UUID, idempotency_key: str
    ) -> KnowledgeRecoveryEvent | None:
        return cast(
            KnowledgeRecoveryEvent | None,
            await self.session.scalar(
                select(KnowledgeRecoveryEvent).where(
                    KnowledgeRecoveryEvent.workspace_id == workspace_id,
                    KnowledgeRecoveryEvent.idempotency_key == idempotency_key,
                )
            ),
        )

    async def active_job(self, workspace_id: UUID, document_id: int) -> IngestionJob | None:
        return cast(
            IngestionJob | None,
            await self.session.scalar(
                select(IngestionJob).where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.document_id == document_id,
                    IngestionJob.status.in_(
                        {"uploading", "awaiting_profile", "queued", "processing", "retry_scheduled"}
                    ),
                )
            ),
        )

    async def version(self, workspace_id: UUID, version_id: int) -> KnowledgeDocumentVersion:
        version = await self.session.scalar(
            select(KnowledgeDocumentVersion).where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.id == version_id,
            )
        )
        if version is None:
            raise RuntimeError("Ingestion job references a missing document version")
        return version

    async def asset(self, workspace_id: UUID, asset_id: int) -> MediaAsset:
        asset = await self.session.scalar(
            select(MediaAsset).where(
                MediaAsset.workspace_id == workspace_id,
                MediaAsset.id == asset_id,
            )
        )
        if asset is None:
            raise RuntimeError("Document version references a missing media asset")
        return asset

    async def active_generation_id(self, workspace_id: UUID, document_id: int) -> int | None:
        return cast(
            int | None,
            await self.session.scalar(
                select(KnowledgeDocumentActiveGeneration.generation_id).where(
                    KnowledgeDocumentActiveGeneration.workspace_id == workspace_id,
                    KnowledgeDocumentActiveGeneration.document_id == document_id,
                )
            ),
        )

    async def latest_document_bundle(
        self, workspace_id: UUID, document_id: int
    ) -> tuple[
        KnowledgeDocument,
        KnowledgeDocumentVersion,
        IngestionJob,
        int | None,
        int | None,
    ] | None:
        document = await self.get_document(workspace_id, document_id)
        if document is None:
            return None
        version = await self.session.scalar(
            select(KnowledgeDocumentVersion)
            .where(
                KnowledgeDocumentVersion.workspace_id == workspace_id,
                KnowledgeDocumentVersion.document_id == document_id,
            )
            .order_by(KnowledgeDocumentVersion.version_no.desc())
            .limit(1)
        )
        job = await self.session.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.workspace_id == workspace_id,
                IngestionJob.document_id == document_id,
            )
            .order_by(IngestionJob.id.desc())
            .limit(1)
        )
        if version is None or job is None:
            raise RuntimeError("Knowledge document is missing its version or ingestion job")
        active_row = (
            await self.session.execute(
                select(
                    KnowledgeDocumentActiveGeneration.generation_id,
                    KnowledgeDocumentVersion.version_no,
                )
                .join(
                    KnowledgeGeneration,
                    KnowledgeGeneration.id == KnowledgeDocumentActiveGeneration.generation_id,
                )
                .join(
                    KnowledgeDocumentVersion,
                    KnowledgeDocumentVersion.id == KnowledgeGeneration.document_version_id,
                )
                .where(
                    KnowledgeDocumentActiveGeneration.workspace_id == workspace_id,
                    KnowledgeDocumentActiveGeneration.document_id == document_id,
                )
            )
        ).one_or_none()
        return (
            document,
            version,
            job,
            active_row.generation_id if active_row is not None else None,
            active_row.version_no if active_row is not None else None,
        )

    async def recent_job_count(self, workspace_id: UUID, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count(IngestionJob.id)).where(
                    IngestionJob.workspace_id == workspace_id,
                    IngestionJob.created_at >= since,
                )
            )
            or 0
        )
