# 10 — Codex backlog (ordered task briefs)

**Status:** F0, F1 and F2 are implemented locally. F2.1 is implemented but its real PostgreSQL integration gate remains pending. F3 and later entries remain future work and are not authorized without an explicit owner request. Break tasks into reviewable changes. For each task: list assumptions, changes, tests run, remaining risks and any proposal needing owner approval.

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

## F2.1 — Universal catalog import (implemented; PostgreSQL gate pending)
- Generalize catalog options/attributes/images and import CSV/XLS/XLSX through one structure-driven pipeline.
- Persist staged records and issues; preview create/update/unchanged/conflict; commit atomically in MERGE mode.
- Keep legacy color/size and CSV endpoints compatible; structured option filters match one actual variant.
- Close the phase only after the migration and PostgreSQL-marked integration suite pass against a dedicated non-production database.

## F2.2 — Workspace locations and catalog scope (implemented; PostgreSQL gate pending)
- Keep one workspace-owned master product/variant identity; never duplicate products by location.
- Store availability and inventory by `(location_id, variant_id)` with `NULL` distinct from zero; location price overrides fall back to existing variant/product pricing.
- Add generic locations, catalog collections, location/collection-scoped search and explicit `location_code` import resolution.
- Do not create agents or agent assignment tables. F3 owns agents and must compose its effective scope from these F2.2 primitives.
- Close the phase only after migration and PostgreSQL integration tests verify stock backfill and composite tenant constraints.

## F3 — Knowledge / agent
- Shop profile/FAQ, PDF/TXT ingestion pipeline with job statuses; embedding adapter and pgvector; agents and KB link; typed tools over the F2.1 catalog/search contract.
- Catalog tools accept generic option/attribute filters, preserve same-variant option semantics, and return authoritative effective price, inventory policy/unknown state, safe image references and legacy color/size only as compatibility projections.
- Done: scoped search, citation refs, no fabricated SKU/stock/discount, no cross-variant option joins, no fashion-only schema assumption and prompt-injection regression tests.

## F4 — Widget / visitor / vision
- Safe embeddable widget, agent publish/origin config, scoped anonymous sessions, conversations, SSE product cards and image upload/vision matching.
- Product cards consume F3 tool output and may show relevant generic options/attributes without requiring size/color, variants or size guides; remote image references must pass the catalog's safe delivery policy and are never fetched during import.
- Done: functional website integration, keyboard/mobile checks, other visitor cannot open conversation, source/card schema tested across product-only and multi-option variant fixtures.

## F5 — Pilot release
- Leads with consent, callback CTA, shop dashboard threads/usage, rate limits/quotas, local observability and documented backup/production prerequisites. Deploy to VPS only in phase P7 when authorized.
- Done: release checklist and owner pilot acceptance; explicitly document storage/PII retention and costs.

## Sample first Codex prompt
"Read AGENTS.md, docs/00-decisions.md, docs/03-architecture.md and docs/10-codex-backlog.md. Work only on F0. Next.js/TypeScript, FastAPI/Python, Supabase Postgres, Supabase Storage, OpenAI and FastAPI-owned email/password auth are confirmed. The application must boot locally now; Docker-on-VPS is later. Propose only genuinely unconfirmed ORM/UI choices before making irreversible decisions. Show exact commands and test results; don't build later features." 
