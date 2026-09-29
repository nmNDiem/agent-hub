from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_hub_api.agents.router import router as agents_router
from agent_hub_api.catalog.router import router as catalog_router
from agent_hub_api.catalog.scope_router import router as catalog_scope_router
from agent_hub_api.catalog.storage import CatalogStorage, SupabaseCatalogStorage
from agent_hub_api.core.config import Settings, get_settings
from agent_hub_api.core.database import create_database_engine, create_session_factory
from agent_hub_api.core.errors import ApiError, api_error_handler
from agent_hub_api.health import router as health_router
from agent_hub_api.identity.dependencies import LoginRateLimiter
from agent_hub_api.identity.email_delivery import EmailDelivery
from agent_hub_api.identity.router import email_router
from agent_hub_api.identity.router import router as auth_router
from agent_hub_api.knowledge.router import router as knowledge_router
from agent_hub_api.knowledge.storage import KnowledgeStorage, SupabaseKnowledgeStorage
from agent_hub_api.workspaces.router import profile_router
from agent_hub_api.workspaces.router import router as workspaces_router


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    email_delivery: EmailDelivery | None = None,
    catalog_storage: CatalogStorage | None = None,
    knowledge_storage: KnowledgeStorage | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    if runtime_settings.email_delivery_enabled and email_delivery is None:
        raise ValueError("Email delivery must be configured when email routes are enabled")
    if catalog_storage is None and (
        runtime_settings.supabase_url is not None
        and runtime_settings.supabase_service_role_key is not None
    ):
        catalog_storage = SupabaseCatalogStorage(
            base_url=runtime_settings.supabase_url,
            service_key=runtime_settings.supabase_service_role_key,
            bucket=runtime_settings.storage_private_bucket,
        )
    if knowledge_storage is None and (
        runtime_settings.supabase_url is not None
        and runtime_settings.supabase_service_role_key is not None
    ):
        knowledge_storage = SupabaseKnowledgeStorage(
            base_url=runtime_settings.supabase_url,
            service_key=runtime_settings.supabase_service_role_key,
            bucket=runtime_settings.storage_private_bucket,
        )
    owned_engine = None
    if session_factory is None and runtime_settings.database_url is not None:
        owned_engine = create_database_engine(runtime_settings.database_url)
        session_factory = create_session_factory(owned_engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_engine is not None:
            await owned_engine.dispose()

    application = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        docs_url="/docs" if runtime_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.session_factory = session_factory
    application.state.email_delivery = email_delivery
    application.state.catalog_storage = catalog_storage
    application.state.knowledge_storage = knowledge_storage
    application.state.login_rate_limiter = LoginRateLimiter()

    @application.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    async def handle_api_error(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, ApiError):
            raise exc
        return await api_error_handler(request, exc)

    application.add_exception_handler(ApiError, handle_api_error)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu gửi lên không hợp lệ.",
                    "request_id": request.state.request_id,
                    "details": {
                        "fields": [
                            {
                                "type": error["type"],
                                "loc": error["loc"],
                                "msg": error["msg"],
                            }
                            for error in exc.errors()
                        ]
                    },
                }
            },
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "request_id": request.state.request_id,
                    "details": {},
                }
            },
        )

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(profile_router)
    application.include_router(workspaces_router)
    application.include_router(agents_router)
    application.include_router(catalog_router)
    application.include_router(catalog_scope_router)
    application.include_router(knowledge_router)
    if runtime_settings.email_delivery_enabled:
        application.include_router(email_router)
    return application


app = create_app()
