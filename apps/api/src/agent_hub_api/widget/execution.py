from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.agents.models import AgentRevision
from agent_hub_api.agents.runtime import AgentExecutionContext
from agent_hub_api.catalog.models import CatalogCollection, Location
from agent_hub_api.catalog.read_models import AuthorizedCatalogScope
from agent_hub_api.knowledge.retrieval import resolve_knowledge_scope_ids


class PublishedCatalogScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_ids: list[int] | None
    collection_ids: list[int] | None


async def resolve_revision_execution_context(
    session: AsyncSession, revision: AgentRevision
) -> AgentExecutionContext:
    """Build a runtime context from an immutable revision and current active resources."""

    try:
        scope = PublishedCatalogScope.model_validate(revision.catalog_scope_json)
    except ValidationError as exc:
        raise RuntimeError("Published agent revision contains invalid catalog scope") from exc

    location_ids: frozenset[int] | None = None
    if scope.location_ids is not None:
        location_ids = frozenset(
            await session.scalars(
                select(Location.id).where(
                    Location.workspace_id == revision.workspace_id,
                    Location.id.in_(scope.location_ids),
                    Location.is_active.is_(True),
                )
            )
        )
    collection_ids: frozenset[int] | None = None
    if scope.collection_ids is not None:
        collection_ids = frozenset(
            await session.scalars(
                select(CatalogCollection.id).where(
                    CatalogCollection.workspace_id == revision.workspace_id,
                    CatalogCollection.id.in_(scope.collection_ids),
                    CatalogCollection.is_active.is_(True),
                )
            )
        )
    knowledge_ids = tuple(item for item in revision.knowledge_base_ids_json if item > 0)
    return AgentExecutionContext(
        workspace_id=revision.workspace_id,
        catalog_scope=AuthorizedCatalogScope(
            workspace_id=revision.workspace_id,
            allowed_location_ids=location_ids,
            allowed_collection_ids=collection_ids,
        ),
        knowledge_scope=await resolve_knowledge_scope_ids(
            session,
            workspace_id=revision.workspace_id,
            knowledge_base_ids=knowledge_ids,
        ),
        locale=revision.default_locale,
        safe_instructions=revision.safe_instructions,
    )
