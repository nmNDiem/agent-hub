# Universal catalog and import

F2.1 uses a generic catalog model. `products` and `product_variants` keep the legacy fields required by authenticated dashboard APIs, while `product_option_definitions`, `product_option_values` and `variant_option_values` are the source of truth for arbitrary options such as Color, Size, Storage, RAM or Flavor. Legacy `color` and `size` are compatibility projections. Flexible, non-identity attributes live in JSONB; SKU, price, stock and option identity remain structured columns/tables.

## Pipeline and file limits

CSV, XLS and XLSX pass through the same logical stages: extraction, profiling, schema/structure resolution, normalization, staging, validation, identity resolution, diff and commit. XLSX is opened in read-only/data-only mode; macros are not executed. Default limits are 10 MB, 20 sheets, 20,000 data rows and 200 columns. The server detects content/signature and does not select a vendor parser.

The extractor preserves four cell states: `missing`, `value`, `blank` and `explicit_null`. Numeric zero and boolean false remain values. During MERGE updates, missing and blank fields keep existing values. Only a reliable explicit-null marker (`NULL`, `#NULL`, `<NULL>`) can clear a nullable field.

HTML descriptions retain source, sanitized HTML and plain text. Imported remote images are syntax-checked HTTP/HTTPS URLs and stored as references; analyze/commit never downloads them.

## Identity, diff and commit

Identity uses canonical ID (when available), confirmed namespaced external reference, then workspace-scoped SKU. Names and semantic similarity never merge products. Untrusted raw external IDs remain evidence only. Analyze writes only to `catalog_import_staged_records` and `catalog_import_issues`; it reports create/update/unchanged/conflict counts.

Commit uses one database transaction, rechecks database uniqueness and identity, and is replay-safe with `Idempotency-Key`. Default mode is MERGE: absence is never delete/archive, and the importer does not perform hard deletion. A conflict or unresolved blocking issue disables commit.

## Structured search

`GET /api/v1/workspaces/{workspace_id}/catalog/search` accepts `text`, `brand`, `price_min`, `price_max`, `in_stock`, repeated `option=Name:Value`, repeated `attribute=Name:Value`, and `limit`. Every request derives tenant access from the authenticated membership. Repeated option filters are correlated against one variant, so `Color=Red` on one variant and `Size=L` on another cannot produce a false Red/L match.

## Tests

Fast tests cover all three formats, alternative CSV encoding/delimiter, cell states, multi-sheet workbooks and the supplied original `products_export_16.7.xls` regression file (14 products, 30 SKU-bearing variants, 29 distinct image URLs). API tests cover tenant denial, staged commit/idempotency and same-variant option matching. PostgreSQL-only checks run under the `postgres` pytest marker with `TEST_DATABASE_URL`; CI migrates PostgreSQL before running them.
