# 10 — Codex backlog (ordered task briefs)

**Important:** This ZIP is design-only. These are instructions for future coding, not claims that features/tests already exist. Break tasks into reviewable PRs. For each task: list assumptions, changes, tests run, remaining risks and any proposal needing owner approval.

## F0 — Repository scaffold
- Read `AGENTS.md` and decision register.
- Propose frontend/ORM/runtime choices for owner sign-off; do not quietly replace confirmed backend/db/storage/auth.
- Scaffold FastAPI app, frontend/widget skeleton if approved, env example, basic health endpoint, lint/format/type/test, migration harness and CI.
- Add README local setup with **actual tested commands**; no real secrets.
- Done: local health test passes, clean CI, one minimal migration dry run.

## F1 — Auth + tenant base
- Build user/workspace/member/session tables/migrations; hashed passwords, verification/reset, access + refresh rotation, RBAC dependencies.
- Implement per-resource workspace scoping and negative tests using two workspaces/users.
- Done: no cross-tenant read/write and no stale refresh token after rotation/logout.

## F2 — Fashion catalog
- Product, variant, size guide and image models/APIs; CSV import with preview/validation, safe Storage files, archive semantics.
- Done: create/import 20+ products, distinguish unknown vs zero stock, correct price across variants; cross-tenant image access denied.

## F3 — Knowledge / agent
- Shop profile/FAQ, PDF/TXT ingestion pipeline with job statuses; embedding adapter and pgvector; agents and KB link; typed tools.
- Done: scoped search, citation refs, no fabricated SKU/stock/discount and prompt-injection regression tests.

## F4 — Widget / visitor / vision
- Safe embeddable widget, agent publish/origin config, scoped anonymous sessions, conversations, SSE product cards and image upload/vision matching.
- Done: functional website integration, keyboard/mobile checks, other visitor cannot open conversation, source/card schema tested.

## F5 — Pilot release
- Leads with consent, callback CTA, shop dashboard threads/usage, rate limits/quotas, local observability and documented backup/production prerequisites. Deploy to VPS only in phase P7 when authorized.
- Done: release checklist and owner pilot acceptance; explicitly document storage/PII retention and costs.

## Sample first Codex prompt
"Read AGENTS.md, docs/00-decisions.md, docs/03-architecture.md and docs/10-codex-backlog.md. Work only on F0. Next.js/TypeScript, FastAPI/Python, Supabase Postgres, Supabase Storage, OpenAI and FastAPI-owned email/password auth are confirmed. The application must boot locally now; Docker-on-VPS is later. Propose only genuinely unconfirmed ORM/UI choices before making irreversible decisions. Show exact commands and test results; don't build later features." 
