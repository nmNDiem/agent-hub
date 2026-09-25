# Screens: products and knowledge

## Products (`/products`)
Table/card toggle; fields `name`, SKU, category/brand, optional price/currency, inventory state, product URL, primary image and last sync/update. Product detail includes optional variants with arbitrary option name/value pairs, SKU, effective price and inventory state, plus non-identity attributes and optional size guide. Legacy color/size fields are displayed as ordinary options. MVP manual CRUD and the documented CSV/XLS/XLSX universal importer share one canonical model; no invented Shopify sync. Product image thumbnails keep natural object-fit with a contained placeholder if missing or unsafe. `Sản phẩm chưa có` offers import/create; enforce workspace SKU uniqueness.

## Catalog import (`/products/import`)
Use a four-step wizard: Analyze → Resolve → Review diff → Commit. Analysis identifies sheets/headers/mappings and persists staged records without changing the catalog. Issues show sheet/row/column, evidence and an explicit resolution control. Diff separates create/update/unchanged/conflict and states that MERGE leaves unmentioned catalog records untouched. Commit requires a stable idempotency key, handles stale/conflict feedback, and preserves the job for retry. Do not present format- or vendor-specific flows when the same behavior applies to CSV/XLS/XLSX.

## Knowledge (`/knowledge`)
Tabs `Tài liệu`, `FAQ`, optionally `Chính sách`; document rows show title, type, source, ingestion state `queued | processing | ready | failed`, chunks count, last processed, error detail/retry. Document action upload up to documented file limit, allowed MIME, progress + cancel, preview parsed text before indexing where feasible. Sources must be associated with shop and selected bots. Delete revokes retrieval and schedules storage cleanup; no stale orphan chunks.

## Product + knowledge relationship
Products are structured data used for recommendations, not files blindly embedded. Size guide and returns policy are explicit documents with retrievable source pointers. Product visibility controls whether chatbot may recommend; unpublished/out-of-stock cannot be recommended as available. Uploaded image becomes asset with private access, potentially public catalog image only after deliberate publication.

## Acceptance
Search/filter uses server-scoped data and multiple option filters bind to one actual variant; product-only records remain usable; image failure is contained; duplicate SKU/option-combination validation and missing-vs-blank behavior are visible; malware/format/type/size failures are visible; ready docs show sources; failed docs cannot be silently used; category/status fields agree with API enums.
