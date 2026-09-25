"""Central ORM model registry used by Alembic and tests."""

from agent_hub_api.catalog.models import (
    CatalogExternalRef,
    CatalogImport,
    CatalogImportIssue,
    CatalogImportMappingProfile,
    CatalogImportStagedRecord,
    Product,
    ProductImage,
    ProductOptionDefinition,
    ProductOptionValue,
    ProductVariant,
    SizeGuide,
    VariantOptionValue,
)
from agent_hub_api.core.database import Base
from agent_hub_api.identity.models import AuthSession, EmailToken, User
from agent_hub_api.workspaces.models import Workspace, WorkspaceMember

__all__ = [
    "AuthSession",
    "Base",
    "CatalogImport",
    "CatalogExternalRef",
    "CatalogImportIssue",
    "CatalogImportMappingProfile",
    "CatalogImportStagedRecord",
    "EmailToken",
    "Product",
    "ProductImage",
    "ProductOptionDefinition",
    "ProductOptionValue",
    "ProductVariant",
    "SizeGuide",
    "VariantOptionValue",
    "User",
    "Workspace",
    "WorkspaceMember",
]
