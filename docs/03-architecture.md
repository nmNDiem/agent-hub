# 03 — Architecture (proposed implementation around confirmed stack)

## Logical flow
```
Shop owner browser --> Dashboard (Next.js + TypeScript CONFIRMED)
                                   |
Website visitor --> Embedded Widget |  (short-lived scoped session)
                   \               /
                     HTTPS / SSE
                       FastAPI
       auth | workspace authorization | abuse limits
               service/use-case layer
       agent orchestration + explicit typed tools
           |         |             |
      Postgres   Supabase Storage  OpenAI
    (Supabase)    (private assets)  (server-side)
       |
  pgvector for semantic search + structured product SQL
```

## Confirmed dependencies
Next.js/TypeScript, FastAPI, Supabase PostgreSQL, Supabase Storage, OpenAI, FastAPI-owned email/password authentication. No Supabase Auth dependency. Local runtime now; Docker-on-VPS later.

## Proposed implementation defaults (require owner approval before irreversible choices)
- Python 3.12+ where supported; FastAPI, Pydantic v2, SQLAlchemy 2 (async or sync selected consistently), Alembic, pytest, Ruff.
- `apps/web` Next.js/TypeScript (**confirmed**); `apps/widget` separately embeddable TS bundle with isolated CSS and minimal dependencies (**packaging proposed**).
- Direct server-side Postgres connection (SQLAlchemy); server-side Supabase Storage SDK/API. Do **not** mistake FastAPI JWT for a Supabase-authenticated client JWT.
- `pgvector` within Supabase PostgreSQL; hybrid retrieval: structured SQL filters plus semantic search for descriptive content.
- Minimal in-process ingestion for tiny pilots only if safe and recoverable; persistent ingestion state in DB. Add an external job queue/worker when workloads warrant it.
- **OpenAI** adapter for chat/vision/embeddings with model IDs, retries, timeouts and API key configured server-side; no extra provider integration in MVP.

## Modules
- `identity`: users, credentials, verification/reset flows, sessions.
- `workspaces`: membership, roles and tenant request context.
- `agents`: configuration, publish state, channel connection.
- `catalog`: products, variants, images, price, stock, sizing and CSV ingestion.
- `knowledge`: documents, source text, chunks, embeddings, ingestion status.
- `conversations`: visitor sessions, messages, SSE and retention.
- `tools`: validated catalog lookup / lead capture.
- `providers`: model API and storage/email adapters.
- `telemetry`: usage, safe audit and health.

## Tenant boundary
Workspace scope is derived from verified dashboard membership or a signed widget session bound to the published agent/workspace. Every repo query filters workspace ID. For Storage path `workspaces/{workspace_id}/...`, authorize before issuing signed URLs. If RLS is configured for direct Postgres access, use a non-bypass role, explicit transaction-scoped trusted identity/tenant context and tests; it is defense in depth, never a substitute for app authorization. Never reuse request-scoped DB sessions across tenants.

## Deployment principles
**Now:** run Next.js and FastAPI locally against isolated development Supabase resources; use local `.env` ignored by Git and `.env.example` without secrets. **Later:** containerize Next.js/FastAPI/worker as needed and run on a VPS behind TLS reverse proxy; Supabase remains hosted DB/Storage. VPS vendor, size and reverse proxy are open details, not a different hosting strategy. Backups, observability and migration gates are required before production.
