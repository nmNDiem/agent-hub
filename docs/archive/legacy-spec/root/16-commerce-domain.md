# 16 — Fashion commerce and extensible business tools

## MVP catalog model
Product (workspace-scoped), optional variants and SKU, generic option definitions/values, non-identity product/variant attributes, price/currency, inventory policy/state, image references, public product URL, trusted external references, optional size chart and category. Products can exist without variants/options and can have multiple images. Generic options are canonical; `color` and `size` remain temporary compatibility projections. Store numeric prices precisely; currency and discount semantics cannot be inferred by an LLM.

## Answer provenance
For price/stock/variant asks, use structured SQL with workspace filters; all requested options must match one actual variant. Effective price is the variant override when present, otherwise the product price. If inventory is unknown or stale, say so; known zero remains out of stock. RAG can explain style/fit or shop policy, but it is **not** authoritative for current price or stock. Product card links must be owner-provided allowlisted URLs. No model-invented product IDs, options, coupons or return guarantees.

## Catalog ingestion
MVP manual CRUD and a structure-driven CSV/XLS/XLSX importer share the canonical write model. Import first persists normalized staging, issues and diff without catalog mutation, then applies an atomic idempotent MERGE after required issues are resolved and affected identities are revalidated. Missing records never imply deletion. Errors identify sheet/row/column where possible. Mapping profiles are structural rather than vendor-specific, and trusted source mappings reconcile by `(workspace, source, external_id)`; names and AI guesses never establish identity. Future live connectors may add explicit reconciliation/deletion policy, inventory freshness and refresh SLAs.

## Size advice
Use product-specific size chart, reported fit and voluntary customer measurements when given. Explain uncertainty for inconsistent charts; avoid guarantees about body fit. Do not require body measurements to use the assistant, and do not persist sensitive attributes without a documented need and notice.

## Future order tools
Read-only order lookup only after verified customer authorization. Order creation, stock mutation, refunds and payment initiation require explicit owner approval, user confirmation, separate permission checks, idempotency keys and complete audit. Never grant such effects just because an LLM generated tool arguments.

## Generalizable tool model
Tool manifest: name/version, purpose, typed input/output, data class, required scope, side-effect classification, confirmation policy, cost policy, audit data. The same gateway may host booking/CRM/ticketing tools later, without making commerce a dependency for every agent.
