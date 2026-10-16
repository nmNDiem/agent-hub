# Catalog

## Function and ownership

Catalog is an optional Commerce capability owning structured product presentation facts. It serves agents and user workflows but is not required to create a Workspace, Agent, knowledge base, or conversation.

## CURRENT

- Products, variants, generic options, locations, current inventory quantities, location price overrides, collections, images, size guides, and namespaced external references.
- Manual management and CSV/XLS/XLSX `Analyze → Resolve → Diff → Commit` import.
- Tenant/location/collection-scoped search and typed agent read tools.

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

## APPROVED DIRECTION

External catalog synchronization may add explicit reconciliation, freshness, recovery, and provider-isolated adapters. Operational inventory evolves separately under [`inventory.md`](inventory.md).

## NOT IMPLEMENTED

No order, checkout, payment, fulfillment, supplier, purchasing, POS, or stock-movement model exists.

## Change trigger

Any workflow that changes stock must first adopt the inventory ledger rules. Any connector must define identity reconciliation and conflict ownership before synchronization.

Related authority: [`commerce.md`](commerce.md), [`inventory.md`](inventory.md), [`../data-model.md`](../data-model.md).
