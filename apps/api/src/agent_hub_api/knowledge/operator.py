from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from uuid import UUID

from agent_hub_api.core.config import Settings, get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.knowledge.profiles import (
    EmbeddingProfileConfiguration,
    KnowledgeProfileService,
)
from agent_hub_api.knowledge.runtime import create_qdrant_index


def _configuration(settings: Settings) -> EmbeddingProfileConfiguration:
    if settings.embedding_model is None or settings.embedding_dimensions is None:
        raise ValueError("EMBEDDING_MODEL and EMBEDDING_DIMENSIONS must be explicitly configured")
    identity = json.dumps(
        {
            "provider": "openai",
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
            "provider_model_revision": settings.embedding_provider_revision,
            "pipeline_version": settings.embedding_pipeline_version,
            "distance_metric": settings.embedding_distance_metric,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return EmbeddingProfileConfiguration(
        provider="openai",
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        provider_model_revision=settings.embedding_provider_revision,
        pipeline_version=settings.embedding_pipeline_version,
        distance_metric=settings.embedding_distance_metric,
        collection=f"{settings.qdrant_collection_prefix}_{suffix}",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentHub knowledge profile operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap-profile")

    activate = commands.add_parser("activate-unprofiled")
    activate.add_argument("--profile-id", type=int, required=True)
    activate.add_argument("--workspace-id", type=UUID, required=True)

    migrate = commands.add_parser("start-migration")
    migrate.add_argument("--workspace-id", type=UUID, required=True)
    migrate.add_argument("--knowledge-base-id", type=int, required=True)
    migrate.add_argument("--target-profile-id", type=int, required=True)
    migrate.add_argument("--operation-id", required=True)

    promote = commands.add_parser("promote")
    promote.add_argument("--workspace-id", type=UUID, required=True)
    promote.add_argument("--knowledge-base-id", type=int, required=True)

    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("--profile-id", type=int, required=True)
    rebuild.add_argument("--operation-id", required=True)
    rebuild.add_argument("--workspace-id", type=UUID)
    return parser


async def _run(args: argparse.Namespace) -> dict[str, int | str]:
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is required")
    engine = create_database_engine(settings)
    vector_index = create_qdrant_index(settings)
    service = KnowledgeProfileService(
        session_factory=create_session_factory(engine),
        settings=settings,
        vector_index=vector_index,
    )
    try:
        if args.command == "bootstrap-profile":
            profile = await service.bootstrap(_configuration(settings))
            return {"profile_id": profile.id, "status": profile.status}
        if args.command == "activate-unprofiled":
            count = await service.activate_unprofiled_bases(
                profile_id=args.profile_id,
                workspace_id=args.workspace_id,
            )
            return {"queued_jobs": count, "status": "ok"}
        if args.command == "start-migration":
            count = await service.start_migration(
                workspace_id=args.workspace_id,
                knowledge_base_id=args.knowledge_base_id,
                target_profile_id=args.target_profile_id,
                operation_id=args.operation_id,
            )
            return {"queued_jobs": count, "status": "ok"}
        if args.command == "promote":
            count = await service.promote(
                workspace_id=args.workspace_id,
                knowledge_base_id=args.knowledge_base_id,
            )
            return {"promoted_documents": count, "status": "ok"}
        if args.command == "rebuild":
            count = await service.queue_rebuild(
                profile_id=args.profile_id,
                operation_id=args.operation_id,
                workspace_id=args.workspace_id,
            )
            return {"queued_jobs": count, "status": "ok"}
        raise RuntimeError("Unsupported command")
    finally:
        await vector_index.close()
        await engine.dispose()


def main() -> None:
    result = asyncio.run(_run(_parser().parse_args()))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
