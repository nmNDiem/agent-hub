# Catalog

## Function and ownership

Catalog is an optional Commerce capability owning structured product presentation facts. It serves agents and user workflows but is not required to create a Workspace, Agent, knowledge base, or conversation.

## CURRENT

- Products, variants, generic options, locations, current inventory quantities, location price overrides, collections, images, size guides, and namespaced external references.
- Manual management and source-agnostic CSV/XLS/XLSX `Analyze → Resolve → Diff → Commit` import. The user supplies a file without first declaring a vendor; profiling and mapping use the file structure.
- Tenant/location/collection-scoped search and typed agent read tools.
- Server-computed workspace capability and bounded Agent scope summaries drive contextual World/navigation presentation; Knowledge-only workspaces do not receive empty Commerce UI.

Main data: catalog entities and persistent import staging/issues/mappings. Main surfaces: Catalog management/import and validated product cards in conversations.

## Core flow

Create or analyze input → resolve identity/mapping issues → review deterministic diff → atomically and idempotently merge → expose only active, authorized records to search/runtime.

## Invariants

- Identity uses canonical IDs, trusted namespaced external references, or workspace-scoped SKU; never names/model guesses.
- Money is exact decimal with explicit currency; zero is valid.
- Effective price is location override, variant override, then product price.
- Inventory `NULL` means unknown and differs from zero.
- Multiple option filters must match one actual variant.
- Import absence never implies deletion and import never fetches arbitrary remote image URLs.
- Import identity and mapping must not depend on a Sapo, KiotViet, Shopify or other vendor label. A sample export may inform generic format handling but cannot turn into a vendor-only parser.

## APPROVED DIRECTION

Import may expand with encoding handling, stronger header/schema inference, validation/normalization, conflict resolution, remembered mappings and clearer staged diffs as concrete files prove the need. External catalog synchronization may add explicit reconciliation, freshness, recovery and provider-isolated adapters. A direct vendor connector is separate from file import. Operational inventory evolves separately under [`inventory.md`](inventory.md).

## NOT IMPLEMENTED

No order, checkout, payment, fulfillment, supplier, purchasing, POS, or stock-movement model exists.

## Change trigger

Any workflow that changes stock must first adopt the inventory ledger rules. Any connector must define identity reconciliation and conflict ownership before synchronization.

## Dependencies and conditional references

- Catalog is bounded by [`commerce.md`](commerce.md); operational quantity changes trigger [`inventory.md`](inventory.md).
- Load [`../data-model.md#catalog-and-current-inventory-view`](../data-model.md#catalog-and-current-inventory-view) only for persistence/schema work.

## Relevant code paths

- `apps/api/src/agent_hub_api/catalog/`
- `apps/web/src/features/catalog/`
- `apps/api/src/agent_hub_api/agents/` only when Catalog read tools/runtime evidence change
