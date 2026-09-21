# Screens: products and knowledge

## Products (`/products`)
Table/card toggle; fields `name`, SKU, category, optional price/currency, availability enum, product URL, primary image, last sync/update. Product detail includes variants (size/color/SKU/stock when known) and optional size guide. MVP manual CRUD or documented CSV import; no invented Shopify sync. Product image thumbnails keep natural object-fit; placeholder if missing. `Sản phẩm chưa có` CTA import/create; invalid imported rows show per-row errors; enforce shop uniqueness on SKU.

## Knowledge (`/knowledge`)
Tabs `Tài liệu`, `FAQ`, optionally `Chính sách`; document rows show title, type, source, ingestion state `queued | processing | ready | failed`, chunks count, last processed, error detail/retry. Document action upload up to documented file limit, allowed MIME, progress + cancel, preview parsed text before indexing where feasible. Sources must be associated with shop and selected bots. Delete revokes retrieval and schedules storage cleanup; no stale orphan chunks.

## Product + knowledge relationship
Products are structured data used for recommendations, not files blindly embedded. Size guide and returns policy are explicit documents with retrievable source pointers. Product visibility controls whether chatbot may recommend; unpublished/out-of-stock cannot be recommended as available. Uploaded image becomes asset with private access, potentially public catalog image only after deliberate publication.

## Acceptance
Search/filter uses server-scoped data; image failure is contained; duplicate SKU validation; malware/format/type/size failures visible; ready docs show sources; failed docs cannot be silently used; category/status fields agree with API enums.
