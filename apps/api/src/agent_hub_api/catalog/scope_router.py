from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.scope_schemas import (
    CollectionCreateRequest,
    CollectionProductResponse,
    CollectionResponse,
    CollectionUpdateRequest,
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
    LocationVariantResponse,
    LocationVariantUpdateRequest,
)
from agent_hub_api.catalog.scope_service import CatalogScopeService
from agent_hub_api.core.database import get_db_session
from agent_hub_api.identity.dependencies import get_current_user, require_csrf
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["catalog-scope"])


def service(session: AsyncSession) -> CatalogScopeService:
    return CatalogScopeService(session)


@router.get("/locations", response_model=list[LocationResponse])
async def list_locations(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    include_archived: bool = False,
) -> list[LocationResponse]:
    return await service(session).list_locations(
        user, workspace_id, include_archived=include_archived
    )


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_location(
    workspace_id: UUID,
    payload: LocationCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LocationResponse:
    return await service(session).create_location(user, workspace_id, payload)


@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location(
    workspace_id: UUID,
    location_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LocationResponse:
    return await service(session).get_location(user, workspace_id, location_id)


@router.patch(
    "/locations/{location_id}",
    response_model=LocationResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_location(
    workspace_id: UUID,
    location_id: int,
    payload: LocationUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LocationResponse:
    return await service(session).update_location(user, workspace_id, location_id, payload)


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def archive_location(
    workspace_id: UUID,
    location_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await service(session).archive_location(user, workspace_id, location_id)


@router.get("/locations/{location_id}/variants", response_model=list[LocationVariantResponse])
async def list_location_variants(
    workspace_id: UUID,
    location_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query: Annotated[str | None, Query(max_length=200)] = None,
    active: bool | None = None,
) -> list[LocationVariantResponse]:
    return await service(session).list_location_variants(
        user, workspace_id, location_id, query=query, active=active
    )


@router.put(
    "/locations/{location_id}/variants/{variant_id}",
    response_model=LocationVariantResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_location_variant(
    workspace_id: UUID,
    location_id: int,
    variant_id: int,
    payload: LocationVariantUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LocationVariantResponse:
    return await service(session).update_location_variant(
        user, workspace_id, location_id, variant_id, payload
    )


@router.get("/catalog/collections", response_model=list[CollectionResponse])
async def list_collections(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    include_archived: bool = False,
) -> list[CollectionResponse]:
    return await service(session).list_collections(
        user, workspace_id, include_archived=include_archived
    )


@router.post(
    "/catalog/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_collection(
    workspace_id: UUID,
    payload: CollectionCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CollectionResponse:
    return await service(session).create_collection(user, workspace_id, payload)


@router.get("/catalog/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    workspace_id: UUID,
    collection_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CollectionResponse:
    return await service(session).get_collection(user, workspace_id, collection_id)


@router.get(
    "/catalog/collections/{collection_id}/products",
    response_model=list[CollectionProductResponse],
)
async def list_collection_products(
    workspace_id: UUID,
    collection_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CollectionProductResponse]:
    return await service(session).list_collection_products(user, workspace_id, collection_id)


@router.patch(
    "/catalog/collections/{collection_id}",
    response_model=CollectionResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_collection(
    workspace_id: UUID,
    collection_id: int,
    payload: CollectionUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CollectionResponse:
    return await service(session).update_collection(user, workspace_id, collection_id, payload)


@router.delete(
    "/catalog/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def archive_collection(
    workspace_id: UUID,
    collection_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await service(session).archive_collection(user, workspace_id, collection_id)


@router.put(
    "/catalog/collections/{collection_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def add_collection_product(
    workspace_id: UUID,
    collection_id: int,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await service(session).set_collection_product(
        user, workspace_id, collection_id, product_id, assigned=True
    )


@router.delete(
    "/catalog/collections/{collection_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def remove_collection_product(
    workspace_id: UUID,
    collection_id: int,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    await service(session).set_collection_product(
        user, workspace_id, collection_id, product_id, assigned=False
    )
