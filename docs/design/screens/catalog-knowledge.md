# Catalog and knowledge

## Catalog

Provide searchable/filterable product list and detail with SKU, category/brand, exact price/currency, variants, generic options/attributes, location inventory, safe images, product URL and lifecycle. Missing price/stock remains visibly unknown.

Import uses `Analyze -> Resolve -> Review diff -> Commit`. Staging never changes canonical rows. Issues identify sheet/row/column and explicit resolution. Diff separates create/update/unchanged/conflict and explains MERGE leaves unmentioned records untouched. Commit preserves the job for safe retry.

## Knowledge

Show knowledge bases/sources, agent assignment and ingestion state. Upload UI displays allowed PDF/TXT limits, progress and stable safe errors. Only ready active generations are presented as searchable. Delete/revoke does not imply external cleanup already succeeded.

Future website/data synchronization appears only when its M2 behavior exists; do not show fake sync freshness.
