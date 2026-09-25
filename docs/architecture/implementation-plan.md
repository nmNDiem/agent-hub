# Implementation detail mapped to master phases

**AUTHORITATIVE phases:** [`../09-roadmap.md`](../09-roadmap.md), [`../10-codex-backlog.md`](../10-codex-backlog.md), [`../22-phase-gates.md`](../22-phase-gates.md). The independently drafted design handoff used another F0–F3 sequence; it is **withdrawn**. Do not pull auth/catalog/RAG/widget into F0.

| Phase | Architecture details | UI/design deliverable |
|---|---|---|
| F0 scaffold | Next.js/TS + FastAPI local boot, env templates, health tests, CI/lint, migration harness, UUIDv7 adapter tests, design tokens; no real auth required | AppShell/sidebar/topbar, responsive skeleton or empty-state preview explicitly marked demo, widget package scaffold only if approved |
| F1 identity/tenants | Custom email/password, verify/reset when delivery configured, rotating refresh sessions, workspace/member tables, tenant negative tests | Real login/register/onboarding/shop switcher, permission-based navigation |
| F2 catalog | BIGINT product/variant PKs, authenticated CRUD/legacy CSV, images in Storage, stock nullable and verified currency | Real catalog UI, product cards, upload/progress and validation UX |
| F2.1 universal catalog | Generic options/attributes/external refs, structure-driven CSV/XLS/XLSX staging/issues/diff, atomic idempotent MERGE and structured search | Analyze → Resolve → Diff → Commit wizard; format-neutral feedback and mapping reuse |
| F3 knowledge/agent | OpenAI adapter, typed tools over F2.1 structured search, pgvector after verified embedding dimension, documents/ingestion jobs, agent config, playground SSE | Real Playground + knowledge UI, grounded sources and schema-neutral product cards, loading/stop/error states |
| F4 web widget/vision | Agent immutable published revisions, public UUIDv7, scoped anonymous sessions, visitor SSE, image upload with quota, F2.1-safe product cards, host CSS isolation | Embeddable, responsive widget matching reference; host-site QA and a11y; conversation view when data exists |
| F5 local pilot | Consented leads, history/usage, limits, observability, privacy/retention acceptance | Data-backed dashboard and inbox, accurate statuses/analytics, error/empty/reporting UX |
| P6+ future | Extra agents/members, VPS via Docker P7, Facebook P8, Zalo P9, advanced inbox P10, billing P11, other domains P12 | Feature-gate inactive modules; never fake a connected status or enable payments from mockup |

**F0 is only successful when local services actually boot and existing applicable tests pass.** Static visual quality alone is not an operational milestone; conversely do not demand a production AI end-to-end experience during F0.

## Implementation status

- F0 scaffold: completed.
- F1 identity/tenants: implemented locally with Argon2id credentials, HttpOnly access/refresh cookies, rotating refresh-token families, CSRF/origin checks, workspace membership enforcement, onboarding and tenant-negative tests. The implementation is organized as `identity` and `workspaces` domain modules; services own transactions and repositories do not commit. Dashboard auth/workspace UI lives under `src/features/`.
- Email verification and recovery routes are registered only when `EMAIL_DELIVERY_ENABLED=true`; a real delivery provider remains required before enabling them outside tests.
- F2 fashion catalog: implemented locally with workspace-scoped product/variant/optional size-guide CRUD, exact Decimal pricing, nullable stock, archived SKU reservation, stable cursor pagination, private image upload/signed URLs with retryable cleanup state, transactional CSV preview/import idempotency, and a responsive catalog dashboard. Supabase Storage credentials and a private bucket are required for real image operations; automated tests use a fake adapter.
- F2.1 universal catalog: implemented with generic catalog relations, legacy color/size compatibility, CSV/XLS/XLSX extraction, persisted staging/issues/mapping profiles, diff, atomic idempotent MERGE, structured same-variant option search and a responsive import wizard. Static checks, non-PostgreSQL tests, builds and offline Alembic SQL generation passed; the dedicated real-PostgreSQL migration/integration gate remains pending, so the phase is not yet closed.
- F3 must consume the F2.1 search/read contracts rather than recreate catalog filtering or depend on legacy color/size columns. F4 consumes the normalized F3 product-card output and must support products without variants, options or size guides.
