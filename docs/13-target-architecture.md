# 13 — Target architecture and module boundaries

## Topology
```
Local (NOW): Next.js dashboard + web widget -> FastAPI -> Supabase Postgres/Storage + OpenAI
Docker/VPS (LATER): reverse proxy/TLS -> Next.js + FastAPI (+ worker when required)
                                  |-> managed Supabase Postgres/Storage
                                  `-> OpenAI API
External channels (LATER) -> verified webhooks -> channel adapters -> conversation service
```
Supabase is the selected database/storage service, **not the chosen auth server or VPS replacement**. Browser clients never receive privileged Supabase or OpenAI credentials.

## Ownership matrix
| Module | Owns | Must not own |
|---|---|---|
| Identity | credentials, verification, sessions, password reset | tenant business data |
| Workspace | membership, roles, tenant settings, access decision | raw passwords |
| Agent | config, versions, allowed tools, publish state | payment execution |
| Knowledge | sources, chunks, indexing and provenance | live stock/price source of truth |
| Catalog | products/variants, sizing, stock, public URL | model-generated prices |
| Conversation | normalized messages, participants, handoff status | platform-specific token semantics |
| Channel adapters | webhook validation, mapping, outbound delivery | independent AI reasoning logic |
| Tool gateway | typed allowlisted actions with audited scope | arbitrary model-executed code |
| Metering/billing | usage events, quota decisions, subscription entitlement | privileged model prompt access by default |
| Operations | telemetry, security audit, retention jobs | customer-visible unreviewed model traces |

## Tenancy and identifiers
Use opaque IDs for workspace, user, agent, channel connection, conversation, source, product and event. Every tenant-owned row has workspace_id or a provably tenant-scoped FK; repository methods take trusted tenant context. Public widget identifiers are not authorization secrets. Membership authorization and short-lived widget sessions are distinct. Audit admin bypasses.

## Processing patterns
- Synchronous read: visitor -> API -> request auth/scope -> catalog/knowledge retrieval -> OpenAI -> SSE answer and product cards.
- Async ingest: file upload -> source row -> processing job -> parse/chunk/embed -> index -> atomic ready/failed state. Retry idempotently; add durable worker if needed, not by default in F0.
- Channel delivery: signed webhook -> deduplicate event -> normalize -> conversation -> agent -> queue/retry outbound. Respect vendor rate limits and permission scopes.
- Model access: single OpenAI adapter initially, config-driven model IDs and per-request budget; adapter seam is not permission to install other providers.

## Design contracts
Define Pydantic DTOs for internal boundaries; publish OpenAPI for external API. Preserve normalized conversation record independent of channel payload. Include request ID/correlation ID for ingestion and outbound events. No shared mutable tenant context. Use additive migrations and compatibility windows for clients/widgets.

## Architecture evolution rules
Prefer modular monolith within FastAPI until observed scale/team constraints justify separate services; do not build a microservice fleet in MVP. Redis/queue and dedicated vector store are optional future optimizations, not confirmed infrastructure. OpenAI may change model IDs without changing exposed business API. See `docs/14-channel-platform.md` and `docs/17-operations-deployment.md`.
