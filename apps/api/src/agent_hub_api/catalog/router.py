from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_hub_api.catalog.schemas import (
    CatalogImportResponse,
    CatalogSearchResponse,
    CleanupResponse,
    ImageResponse,
    ImageUrlResponse,
    ImportCommitResponse,
    ImportPreviewResponse,
    ProductCreateRequest,
    ProductDetailResponse,
    ProductListResponse,
    ProductUpdateRequest,
    ResolveImportIssueRequest,
    SizeGuideRequest,
    SizeGuideResponse,
    UniversalImportCommitResponse,
    VariantCreateRequest,
    VariantResponse,
    VariantUpdateRequest,
)
from agent_hub_api.catalog.service import CatalogService
from agent_hub_api.catalog.storage import CatalogStorage, UnavailableCatalogStorage
from agent_hub_api.catalog.universal_service import UniversalCatalogService
from agent_hub_api.core.config import Settings
from agent_hub_api.core.database import get_db_session
from agent_hub_api.core.errors import ApiError
from agent_hub_api.identity.dependencies import (
    get_current_user,
    get_request_settings,
    require_csrf,
)
from agent_hub_api.identity.models import User

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["catalog"])


def get_catalog_storage(request: Request) -> CatalogStorage:
    storage: CatalogStorage | None = getattr(request.app.state, "catalog_storage", None)
    return storage or UnavailableCatalogStorage()


def service(session: AsyncSession, settings: Settings, storage: CatalogStorage) -> CatalogService:
    return CatalogService(session, settings, storage)


def universal_service(session: AsyncSession, settings: Settings) -> UniversalCatalogService:
    return UniversalCatalogService(session, settings)


@router.post(
    "/catalog/imports",
    response_model=CatalogImportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_catalog_import(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    file: Annotated[UploadFile, File()],
) -> CatalogImportResponse:
    content = await file.read(settings.catalog_import_max_bytes + 1)
    return await universal_service(session, settings).create_and_analyze(
        user, workspace_id, file.filename or "catalog", content
    )


@router.get("/catalog/imports/{import_id}", response_model=CatalogImportResponse)
async def get_catalog_import(
    workspace_id: UUID,
    import_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> CatalogImportResponse:
    return await universal_service(session, settings).get(user, workspace_id, import_id)


@router.post(
    "/catalog/imports/{import_id}/issues/{issue_id}/resolve",
    response_model=CatalogImportResponse,
    dependencies=[Depends(require_csrf)],
)
async def resolve_catalog_import_issue(
    workspace_id: UUID,
    import_id: int,
    issue_id: int,
    payload: ResolveImportIssueRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> CatalogImportResponse:
    return await universal_service(session, settings).resolve(
        user, workspace_id, import_id, issue_id, payload
    )


@router.post(
    "/catalog/imports/{import_id}/commit",
    response_model=UniversalImportCommitResponse,
    dependencies=[Depends(require_csrf)],
)
async def commit_catalog_import_job(
    workspace_id: UUID,
    import_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> UniversalImportCommitResponse:
    return await universal_service(session, settings).commit(
        user, workspace_id, import_id, idempotency_key
    )


@router.get("/catalog/search", response_model=CatalogSearchResponse)
async def search_catalog(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    text: Annotated[str | None, Query(max_length=200)] = None,
    brand: Annotated[str | None, Query(max_length=160)] = None,
    price_min: Annotated[Decimal | None, Query(ge=0)] = None,
    price_max: Annotated[Decimal | None, Query(ge=0)] = None,
    in_stock: bool | None = None,
    location_id: Annotated[int | None, Query(ge=1)] = None,
    collection_id: Annotated[int | None, Query(ge=1)] = None,
    option: Annotated[list[str] | None, Query()] = None,
    attribute: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CatalogSearchResponse:
    return await universal_service(session, settings).search(
        user,
        workspace_id,
        text=text,
        brand=brand,
        price_min=price_min,
        price_max=price_max,
        in_stock=in_stock,
        location_id=location_id,
        collection_id=collection_id,
        options=option or [],
        attributes=attribute or [],
        limit=limit,
    )


@router.get("/products", response_model=ProductListResponse)
async def list_products(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    product_status: Annotated[Literal["active", "archived"] | None, Query(alias="status")] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
) -> ProductListResponse:
    return await service(session, settings, storage).list_products(
        user,
        workspace_id,
        limit=limit,
        cursor=cursor,
        product_status=product_status,
        category=category,
        query=query,
    )


@router.post(
    "/products",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_product(
    workspace_id: UUID,
    payload: ProductCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> ProductDetailResponse:
    return await service(session, settings, storage).create_product(user, workspace_id, payload)


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    workspace_id: UUID,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> ProductDetailResponse:
    return await service(session, settings, storage).get_product(user, workspace_id, product_id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_product(
    workspace_id: UUID,
    product_id: int,
    payload: ProductUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> ProductDetailResponse:
    return await service(session, settings, storage).update_product(
        user, workspace_id, product_id, payload
    )


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def archive_product(
    workspace_id: UUID,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> None:
    await service(session, settings, storage).archive_product(user, workspace_id, product_id)


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_variant(
    workspace_id: UUID,
    product_id: int,
    payload: VariantCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> VariantResponse:
    return await service(session, settings, storage).create_variant(
        user, workspace_id, product_id, payload
    )


@router.patch(
    "/products/{product_id}/variants/{variant_id}",
    response_model=VariantResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_variant(
    workspace_id: UUID,
    product_id: int,
    variant_id: int,
    payload: VariantUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> VariantResponse:
    return await service(session, settings, storage).update_variant(
        user, workspace_id, product_id, variant_id, payload
    )


@router.delete(
    "/products/{product_id}/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def archive_variant(
    workspace_id: UUID,
    product_id: int,
    variant_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> None:
    await service(session, settings, storage).archive_variant(
        user, workspace_id, product_id, variant_id
    )


@router.put(
    "/products/{product_id}/size-guide",
    response_model=SizeGuideResponse,
    dependencies=[Depends(require_csrf)],
)
async def put_size_guide(
    workspace_id: UUID,
    product_id: int,
    payload: SizeGuideRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> SizeGuideResponse:
    return await service(session, settings, storage).put_size_guide(
        user, workspace_id, product_id, payload
    )


@router.delete(
    "/products/{product_id}/size-guide",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_size_guide(
    workspace_id: UUID,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> None:
    await service(session, settings, storage).delete_size_guide(user, workspace_id, product_id)


@router.post(
    "/products/{product_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_image(
    workspace_id: UUID,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
    file: Annotated[UploadFile, File()],
    variant_id: Annotated[int | None, Form()] = None,
    alt_text: Annotated[str | None, Form(max_length=300)] = None,
    sort_order: Annotated[int, Form(ge=0, le=10_000)] = 0,
) -> ImageResponse:
    content = await file.read(settings.catalog_image_max_bytes + 1)
    return await service(session, settings, storage).upload_image(
        user,
        workspace_id,
        product_id,
        content=content,
        filename=file.filename or "image",
        declared_content_type=file.content_type or "application/octet-stream",
        variant_id=variant_id,
        alt_text=alt_text,
        sort_order=sort_order,
    )


@router.get("/products/{product_id}/images/{image_id}/signed-url", response_model=ImageUrlResponse)
async def get_image_url(
    workspace_id: UUID,
    product_id: int,
    image_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> ImageUrlResponse:
    return await service(session, settings, storage).get_image_url(
        user, workspace_id, product_id, image_id
    )


@router.delete(
    "/products/{product_id}/images/{image_id}",
    response_model=CleanupResponse,
    dependencies=[Depends(require_csrf)],
)
async def delete_image(
    workspace_id: UUID,
    product_id: int,
    image_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> CleanupResponse:
    return await service(session, settings, storage).delete_image(
        user, workspace_id, product_id, image_id
    )


@router.post(
    "/products/{product_id}/images/{image_id}/cleanup",
    response_model=CleanupResponse,
    dependencies=[Depends(require_csrf)],
)
async def retry_image_cleanup(
    workspace_id: UUID,
    product_id: int,
    image_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
) -> CleanupResponse:
    return await service(session, settings, storage).retry_image_cleanup(
        user, workspace_id, product_id, image_id
    )


async def read_csv(file: UploadFile, settings: Settings) -> bytes:
    allowed = {"text/csv", "application/csv", "application/vnd.ms-excel"}
    if file.content_type not in allowed:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "INVALID_CSV_TYPE",
            "Tá»‡p import pháº£i lÃ  CSV.",
        )
    return await file.read(settings.catalog_csv_max_bytes + 1)


@router.post(
    "/catalog/import/preview",
    response_model=ImportPreviewResponse,
    dependencies=[Depends(require_csrf)],
)
async def preview_import(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
    file: Annotated[UploadFile, File()],
) -> ImportPreviewResponse:
    return await service(session, settings, storage).preview_import(
        user, workspace_id, await read_csv(file, settings)
    )


@router.post(
    "/catalog/import",
    response_model=ImportCommitResponse,
    dependencies=[Depends(require_csrf)],
)
async def commit_import(
    workspace_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    storage: Annotated[CatalogStorage, Depends(get_catalog_storage)],
    file: Annotated[UploadFile, File()],
    preview_sha256: Annotated[str, Form(min_length=64, max_length=64)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> ImportCommitResponse:
    return await service(session, settings, storage).commit_import(
        user,
        workspace_id,
        content=await read_csv(file, settings),
        preview_sha256=preview_sha256,
        idempotency_key=idempotency_key,
    )
