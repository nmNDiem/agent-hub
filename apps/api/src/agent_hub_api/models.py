"""Central ORM model registry used by Alembic and tests."""

from agent_hub_api.agents.models import Agent, AgentCatalogCollection, AgentLocation
from agent_hub_api.catalog.models import (
    CatalogCollection,
    CatalogCollectionProduct,
    CatalogExternalRef,
    CatalogImport,
    CatalogImportIssue,
    CatalogImportMappingProfile,
    CatalogImportStagedRecord,
    InventoryLevel,
    Location,
    LocationVariant,
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
    "Agent",
    "AgentCatalogCollection",
    "AgentLocation",
    "AuthSession",
    "Base",
    "CatalogImport",
    "CatalogCollection",
    "CatalogCollectionProduct",
    "CatalogExternalRef",
    "CatalogImportIssue",
    "CatalogImportMappingProfile",
    "CatalogImportStagedRecord",
    "EmailToken",
    "InventoryLevel",
    "Location",
    "LocationVariant",
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
