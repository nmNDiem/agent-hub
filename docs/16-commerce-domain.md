# 16 — Fashion commerce and extensible business tools

## MVP catalog model
Product (shop-scoped), variant (SKU, color, size), price/currency, inventory state, product image(s), public product URL, availability timestamp/source, optional size chart and category. Products can have variants and multiple images. Store numeric prices precisely; currency and discount semantics cannot be inferred by LLM.

## Answer provenance
For price/stock/variant asks, use structured SQL with workspace filters; if data is missing or stale, say so. RAG can explain style/fit or shop policy, but it is **not** authoritative for current price or stock. Product card links must be owner-provided allowlisted URLs. No model-invented product IDs, coupons or return guarantees.

## Catalog ingestion
MVP manual CRUD and validated CSV; validation errors should identify row/column and never partially corrupt an existing catalog. Provide explicit duplicate SKU policy, transactional import and import summary. Future commerce integrations use source mapping and idempotent upsert by `(workspace, provider, external_id)`, reconcile deletions/unavailable variants, detect stale inventory and specify refresh SLA.

## Size advice
Use product-specific size chart, reported fit and voluntary customer measurements when given. Explain uncertainty for inconsistent charts; avoid guarantees about body fit. Do not require body measurements to use the assistant, and do not persist sensitive attributes without a documented need and notice.

## Future order tools
Read-only order lookup only after verified customer authorization. Order creation, stock mutation, refunds and payment initiation require explicit owner approval, user confirmation, separate permission checks, idempotency keys and complete audit. Never grant such effects just because an LLM generated tool arguments.

## Generalizable tool model
Tool manifest: name/version, purpose, typed input/output, data class, required scope, side-effect classification, confirmation policy, cost policy, audit data. The same gateway may host booking/CRM/ticketing tools later, without making commerce a dependency for every AgentHub agent.
