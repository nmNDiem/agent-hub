# 10 — Codex backlog (ordered task briefs)

**Status:** F0 through F2.2 and F3.1 through F3.3 are complete. Critical PostgreSQL gates use the isolated `agenthub_test` schema; F3.3 also passed against an explicitly configured non-production Qdrant Cloud collection. F3.4 and later entries remain future work and are not authorized without an explicit owner request. F3 remains open until every F3 slice passes together. Break tasks into reviewable changes. For each task: list assumptions, changes, tests run, remaining risks and any proposal needing owner approval.

## F0 — Repository scaffold (complete)
- Read `AGENTS.md` and decision register.
- Propose frontend/ORM/runtime choices for owner sign-off; do not quietly replace confirmed backend/db/storage/auth.
- Scaffold FastAPI app, frontend/widget skeleton if approved, env example, basic health endpoint, lint/format/type/test, migration harness and CI.
- Add README local setup with **actual tested commands**; no real secrets.
- Done: local health test passes, clean CI, one minimal migration dry run.

## F1 — Auth + tenant base (complete)
- Build user/workspace/member/session tables/migrations; hashed passwords, verification/reset, access + refresh rotation, RBAC dependencies.
- Implement per-resource workspace scoping and negative tests using two workspaces/users.
- Organize the backend as `agent_hub_api.identity` and `agent_hub_api.workspaces` domain modules,
  with shared infrastructure in `agent_hub_api.core`; services own transaction boundaries and
  repositories do not commit. Keep the central ORM registry for Alembic.
- Done: no cross-tenant read/write and no stale refresh token after rotation/logout.

## F2 — Fashion catalog (complete)
- Product, variant, size guide and image models/APIs; CSV import with preview/validation, safe Storage files, archive semantics.
- Done: create/import 20+ products, distinguish unknown vs zero stock, correct price across variants; cross-tenant image access denied.

## F2.1 — Universal catalog import (complete)
- Generalize catalog options/attributes/images and import CSV/XLS/XLSX through one structure-driven pipeline.
- Persist staged records and issues; preview create/update/unchanged/conflict; commit atomically in MERGE mode.
- Keep legacy color/size and CSV endpoints compatible; structured option filters match one actual variant.
- Close the phase only after the critical PostgreSQL-marked integration suite passes in the isolated `agenthub_test` schema of the local/test `DATABASE_URL`. Broader PostgreSQL coverage is deferred to pre-release hardening.

## F2.2 — Workspace locations and catalog scope (complete)
- Keep one workspace-owned master product/variant identity; never duplicate products by location.
- Store availability and inventory by `(location_id, variant_id)` with `NULL` distinct from zero; location price overrides fall back to existing variant/product pricing.
- Add generic locations, catalog collections, location/collection-scoped search and explicit `location_code` import resolution.
- Do not create agents or agent assignment tables. F3 owns agents and must compose its effective scope from these F2.2 primitives.
- Close the phase only after migration and PostgreSQL integration tests verify stock backfill and composite tenant constraints.

## F3 — Knowledge / agent

F3 is one roadmap phase and release gate, implemented through the following ordered task briefs. Completing an individual task does not authorize F4 or mark F3 complete.

### F3.1 — Agent foundation and catalog tools (complete)
- Add agent/config persistence and location/collection assignments.
- Resolve caller authorization into an immutable allowed catalog scope before query execution. Query intent can only narrow that scope; never pass dashboard `User` into the catalog query engine.
- Build typed tools over `CatalogReadService`. Accept generic option/attribute filters, preserve same-variant option semantics and return authoritative effective price, inventory policy/unknown state, safe image references and legacy color/size only as compatibility projections.
- Done: cross-workspace and scope-narrowing tests pass; product candidates are limited before batched hydration; no cross-variant option joins or fashion-only schema assumptions.

### F3.2 — Knowledge persistence and ingestion (complete)
- Add shop profile/FAQ, knowledge bases and agent links, document, chunk and ingestion-job persistence plus immutable embedding-profile metadata in Postgres.
- Implement safe PDF/TXT extraction, chunking, job status transitions and idempotent retry boundaries. Treat files and extracted content as untrusted data.
- Keep the pipeline testable with fake embedding/vector adapters; do not require Qdrant or OpenAI for persistence and ingestion unit tests.
- Done: invalid-file and retry behavior, active-generation rules and negative cross-workspace tests pass without external providers.

### F3.3 — Embedding and Qdrant retrieval (complete)
- Implement `EmbeddingProvider` with OpenAI as the initial implementation and Qdrant behind `KnowledgeVectorIndex`, following ADR-0002. Do not implement Gemini or another provider without a separately approved task.
- Keep Qdrant a rebuildable derived index shared across tenants by profile. Index post-transactionally and idempotently; inject workspace/allowed-source filters server-side and revalidate results against active Postgres rows.
- Add rebuild/re-index behavior, citation references, batched embedding/index operations and explicit vector-outage behavior.
- Done: a real explicitly configured non-production Qdrant integration proves tenant isolation, stale/revoked points are rejected and indexing retries are safe.

### F3.4 — Grounded agent runtime
- Implement the OpenAI generation adapter and simple orchestration across knowledge retrieval and catalog tools.
- Produce grounded source references and normalized schema-neutral product-card output for F4; catalog facts must come from typed tools at answer time.
- Enforce prompt-injection defenses, bounded token/tool usage and safe errors without leaking prompts, credentials or private data.
- Done: regressions prove no fabricated SKU/stock/price/discount or business commitment, correct unknown inventory behavior, generic option support and bounded usage/cost.

### F3.5 — Dashboard knowledge UI and Playground
- Add knowledge upload/status/error UI, agent configuration UI and an authenticated Playground using SSE.
- Render grounded sources and schema-neutral product cards with loading, stop, empty and error states.
- Done: the integrated dashboard flow passes accessibility and cancellation/error checks; source/card fixtures cover product-only and multi-option catalogs.

### F3 phase completion
- Close F3 only after F3.1 through F3.5 pass together and the F3 exit evidence in `22-phase-gates.md` is recorded.

## F4 — Widget / visitor / vision
- Safe embeddable widget, agent publish/origin config, scoped anonymous sessions, conversations, SSE product cards and image upload/vision matching.
- Product cards consume F3 tool output and may show relevant generic options/attributes without requiring size/color, variants or size guides; remote image references must pass the catalog's safe delivery policy and are never fetched during import.
- Done: functional website integration, keyboard/mobile checks, other visitor cannot open conversation, source/card schema tested across product-only and multi-option variant fixtures.

## F5 — Pilot release
- Leads with consent, callback CTA, shop dashboard threads/usage, rate limits/quotas, local observability and documented backup/production prerequisites. Deploy to VPS only in phase P7 when authorized.
- Done: release checklist and owner pilot acceptance; explicitly document storage/PII retention and costs.

## Sample first Codex prompt
"Read AGENTS.md, docs/00-decisions.md, docs/03-architecture.md and docs/10-codex-backlog.md. Work only on F0. Next.js/TypeScript, FastAPI/Python, Supabase Postgres, Supabase Storage, OpenAI and FastAPI-owned email/password auth are confirmed. The application must boot locally now; Docker-on-VPS is later. Propose only genuinely unconfirmed ORM/UI choices before making irreversible decisions. Show exact commands and test results; don't build later features." 
