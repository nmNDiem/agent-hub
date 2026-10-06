# Catalog

## Purpose

The catalog is the authoritative structured source for products, variants, options, price, inventory and safe presentation references. It is useful to commerce agents but is not a dependency of every AgentHub agent.

## Current capability

- Workspace master products and optional variants.
- Generic option definitions/values and flexible non-identity attributes.
- Locations, per-location inventory/price overrides and collections.
- Private managed images or recorded remote references with safe delivery rules.
- Manual CRUD and one structure-driven CSV/XLS/XLSX Analyze -> Resolve -> Diff -> Commit importer.
- Tenant/location/collection-scoped search and typed agent read tools.

## Complete domain capability

- External commerce/catalog connections with explicit identity reconciliation.
- Scheduled synchronization, freshness status and failure recovery.
- Provider-specific mapping isolated behind connector adapters.
- Deliberate deletion/archive semantics and conflict review.

## Truth and identity rules

- Product/variant identity comes from canonical IDs, trusted namespaced external references or workspace-scoped SKU; names and model guesses never merge records.
- Generic options are canonical; legacy color/size fields are compatibility projections.
- Exact price uses `NUMERIC(18,2)`/`Decimal` with explicit ISO currency.
- Effective price is location override, then variant override, then product price; zero is valid.
- Inventory `NULL` means unknown and differs from known zero.
- Multiple option filters must match the same actual variant.
- Import MERGE never treats absence from a file as deletion.
- Import analysis/commit never fetches arbitrary remote image URLs.

Detailed entities and API contracts are in [`../reference/data-model.md`](../reference/data-model.md) and [`../reference/api.md`](../reference/api.md).
