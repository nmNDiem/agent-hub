# Architecture — Agent Hub

**Authority:** `../00-decisions.md` is the owner decision register; `../04-data-model.md` the logical full MVP entity scope; `../05-api-contract.md` owns endpoint families and SSE names; `../09-roadmap.md`/`../10-codex-backlog.md`/`../22-phase-gates.md` own F0–F5/P6+ numbering. This folder gives implementation detail, not a second roadmap/route registry. Here `workspace` = shop for fashion UI; `agent` = chatbot for UI.

## Architecture in one paragraph
Next.js App Router renders admin and delivers static widget assets; FastAPI is the **only domain/business and authentication API**; Supabase PostgreSQL persists relational data and pgvector retrieval; Supabase Storage holds shop documents and pictures; a server-side OpenAI adapter handles generation, embeddings and image understanding. Web widget calls **published/publicly safe** bot endpoints; admins call authenticated shop-scoped endpoints. Future Facebook/Zalo adapters map inbound messages to the same conversation service. Local development now, Docker/VPS deploy later.

## Documents
`../00-decisions.md` — decisions/exclusions; `system-context.md` — diagram, modules, dependency direction; `identifiers.md` — BIGINT / UUIDv7; `data-model.md` — tables/indexes; `sql/001_reference_schema.sql` — reference DDL, not blindly a finished production migration; `auth-and-tenancy.md` — own email/password, tenancy; `api-conventions.md` — pagination, SSE, errors (routes live in `../05-api-contract.md`); `ai-rag-vision.md` — prompts/retrieval/vision; `storage-and-ingestion.md` — secure storage; `channels-and-widget.md` — widget and channel abstraction; `frontend.md` — Next.js architecture; `security-operations.md` — threat checklist, logs, monitoring, cost; `local-deployment.md` — dev and production migration; `testing.md` — test matrix; `implementation-plan.md` — detail mapped to canonical F0–F5 phases; `adr/0001-foundational-decisions.md` — decision record.

## Dependency boundaries
`UI -> typed API client -> FastAPI routers -> domain services -> repositories/providers`. Never let Next.js browser connect directly to privileged PostgreSQL/Supabase Storage or OpenAI. Domain services depend on OpenAI/Storage interfaces; channel adapters depend on core chat, not vice versa. Generated OpenAPI is backend-owned contract (with stable revision), frontend types regenerated on CI.

The FastAPI package is a domain-oriented modular monolith. Current business modules are
`agent_hub_api.identity` and `agent_hub_api.workspaces`; do not create future modules before their
phase needs them. Within a domain, routers own the HTTP boundary, services own business rules,
authorization and transaction orchestration, and repositories own persistence queries without
committing. `agent_hub_api.core` contains shared infrastructure only. The root `models.py` is the
central ORM registry imported by Alembic so every domain model contributes to `Base.metadata`;
migrations remain in `apps/api/migrations`.

## Deployment principle
No premature K8s, Celery, microservices or paid queue for MVP. Introduce a simple persisted job runner to avoid slow HTTP document ingestion; migrate to worker process/queue if scale requires. Avoid `BackgroundTasks` as only guarantee for important jobs that must survive restarts.
