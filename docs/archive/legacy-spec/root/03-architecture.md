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
      Postgres   Supabase Storage  Qdrant       OpenAI
    (Supabase)    (private assets) (vectors)   (server-side)
       |
  structured product SQL; Qdrant indexes knowledge chunks
```

## Confirmed dependencies
Next.js/TypeScript, FastAPI, Supabase PostgreSQL, Supabase Storage, Qdrant, OpenAI, FastAPI-owned email/password authentication. No Supabase Auth dependency. Local runtime now; Docker-on-VPS later.

## Proposed implementation defaults (require owner approval before irreversible choices)
- Python 3.12+ where supported; FastAPI, Pydantic v2, SQLAlchemy 2 (async or sync selected consistently), Alembic, pytest, Ruff.
- `apps/web` Next.js/TypeScript (**confirmed**); `apps/widget` is the separately built, embeddable TypeScript IIFE implemented under the approved F4 scope, with Shadow DOM isolation and no dashboard runtime dependency.
- Direct server-side Postgres connection (SQLAlchemy); server-side Supabase Storage SDK/API. Do **not** mistake FastAPI JWT for a Supabase-authenticated client JWT.
- Qdrant is the vector index for descriptive knowledge; Supabase PostgreSQL remains authoritative for documents, chunks, ingestion jobs and active embedding profiles. Hybrid retrieval combines structured catalog SQL with Qdrant semantic search.
- Minimal in-process ingestion for tiny pilots only if safe and recoverable; persistent ingestion state in DB. Add an external job queue/worker when workloads warrant it.
- **OpenAI** is the initial chat/vision/embedding implementation behind separate model and embedding-provider interfaces. Persist embedding provider/model/dimensions/revision metadata; no extra provider integration in MVP.

## Modules
- `identity`: users, credentials, verification/reset flows, sessions.
- `workspaces`: membership, roles and tenant request context.
- `agents`: configuration, publish state, channel connection.
- `catalog`: workspace master products/variants, generic options/attributes, images, locations, location-scoped inventory/pricing, collections, optional sizing and universal CSV/XLS/XLSX ingestion/search. Agent assignments are composed later in the `agents` domain rather than owned by catalog.
- `knowledge`: documents, source text, chunks, embedding profiles/index state and ingestion status; it depends on provider-neutral embedding and vector-index interfaces.
- `conversations`: visitor sessions, messages, SSE and retention.
- `tools`: validated catalog lookup / lead capture.
- `providers`: model API and storage/email adapters.
- `telemetry`: usage, safe audit and health.

## Tenant boundary
Workspace scope is derived from verified dashboard membership or an opaque short-lived widget session bound to the published revision, agent, workspace and exact request origin. Every Postgres query and Qdrant search filters a server-validated workspace ID; Qdrant payload indexes mark it as the tenant field. For Storage path `workspaces/{workspace_id}/...`, authorize before issuing signed URLs. Widget product images use expiring session-scoped grants before the backend issues a private Storage redirect; visitor images remain private and are never exposed by object key. If RLS is configured for direct Postgres access, use a non-bypass role, explicit transaction-scoped trusted identity/tenant context and tests; it is defense in depth, never a substitute for app authorization. Never reuse request-scoped DB sessions across tenants.

## Deployment principles
**Now:** run Next.js and FastAPI locally against isolated development Supabase resources; use local `.env` ignored by Git and `.env.example` without secrets. **Later:** containerize Next.js/FastAPI/worker as needed and run on a VPS behind TLS reverse proxy; Supabase remains hosted DB/Storage. VPS vendor, size and reverse proxy are open details, not a different hosting strategy. Backups, observability and migration gates are required before production.
