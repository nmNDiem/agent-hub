# Verification matrix

| Layer | Required tests |
|---|---|
| IDs | generated UUID.version=7; BIGINT identity insert; no uuidv4/default v4 regressions; copy/public IDs round-trip |
| Auth | signup/login/logout/refresh rotation/reuse; generic failures; cookie attrs, CSRF, redirect safety |
| Tenancy | shop A member cannot list/get/mutate shop B bot, conversation, product, doc or Storage asset; cross-shop RAG fixture |
| DB | Alembic upgrade on clean DB, unique constraints, FK match, deletion/archival and tenancy indexes |
| Catalog import | CSV/XLS/XLSX shared extraction; cell-state semantics; staged diff; mapping fingerprint stability; identity/SKU conflicts; atomic idempotent MERGE; original XLS regression |
| Catalog search | generic options/attributes; all options on one actual variant; effective price fallback; unknown vs zero stock; product-only records; cross-workspace denial |
| AI | fake-provider deterministic stream, timeout/abort/retry, actual source IDs only, no hallucinated product, image reject |
| Knowledge | MIME/size/signature, corrupt PDF, no-text PDF, retries/idempotency, remove revokes chunks, no partial ready |
| Widget | published vs draft, invalid origin, brute-force quota, session binding, mobile focus/host CSS isolation |
| UI | user journeys, empty/error/loading, shop switching, filter URL, voice of Vietnamese strings, contrast/responsive |
| Ops | health, secret redaction, per-shop token cap, metric definitions and log request IDs |

## Test fixture protocol
Never use mockup `bot_0198...` strings as real IDs. Generate UUIDv7 at fixture creation, seed 2 workspaces with similar product names, overlapping SKUs/options and 2 agents to prove isolation. Include product-only and multi-variant fixtures where different variants individually satisfy different filters, so false cross-variant matches are detectable. Internal BIGINTs are left to DB identity. Fake model, embedding-provider and vector-index adapters keep offline tests free/fast; opt-in real-provider smoke tests are explicitly budgeted and never mandatory CI. F3's Qdrant integration uses the explicitly configured non-production Qdrant Cloud cluster and a random `_test_` collection to verify mandatory tenant/source filters, stale-generation rejection and idempotent upsert/delete; cleanup deletes only that exact collection. Separate database-backed tests verify Postgres revalidation and profile cutover between different fake dimensions. PostgreSQL-specific constraints and migrations run against a dedicated non-production PostgreSQL database at their phase gates.

## Demo is not done
A pretty static dashboard without local boot, migration harness and working test tools does **not** satisfy foundation acceptance. Authentication must include real tenant isolation. A hardcoded AI reply does not satisfy grounded-agent acceptance. Simulated `Connected` Facebook/Zalo badges do not count as channels. Reference images are layout targets, not functional acceptance evidence.
