# API and event contracts

FastAPI publishes the executable OpenAPI contract. Load this reference only when an external HTTP, SSE, DTO, error, pagination, authentication or idempotency contract may change. Current paths remain defined by generated OpenAPI and existing clients.

All route families below are **CURRENT** unless explicitly labeled otherwise. AgentHub has no generic capability-registration or effectful-Agent-action API today.

## General conventions

- Prefix: `/api/v1`; JSON/UTF-8; ISO-8601 UTC timestamps.
- Dashboard routes use FastAPI cookies, CSRF protection for unsafe methods and server-verified workspace membership.
- Public channels derive workspace/Agent/conversation scope from an opaque session or verified server-owned connection, never request tenant fields.
- Prices serialize as exact decimal strings with ISO currency. `null` remains unknown and is never converted to zero.
- Lists use opaque cursor pagination: `{"items": [], "next_cursor": null}` with bounded limits and allowlisted filters/sorts.
- Errors use `{"error":{"code":"...","message":"...","request_id":"...","details":{}}}` with safe details.
- Use 401 for missing/invalid authentication, 403 for denied action, non-leaking 404 for hidden tenant resources, 409 for state conflict, 413 for size, 415 for media, 422 for validation, 429 for limits and 503 for unavailable dependencies.
- Idempotency keys are scoped to the authenticated actor/workspace or public session/connection and checked against a request hash.

## Current route families

| Family | Main operations |
|---|---|
| Health | `/health`, `/health/live`, `/health/ready` |
| Auth | register, login, refresh, logout, verification/recovery and `/me` |
| Workspaces | list/create/read/update workspace and current membership context |
| Agents | CRUD configuration, Catalog/Knowledge assignments, publish, pause, Website configuration and Playground stream |
| Catalog | products, variants, size guides, images, locations, collections, imports and structured search |
| Knowledge | bases, immutable document replacement/history/review, ingestion retry/rebuild, ephemeral retrieval diagnostics, archive and Agent assignments |
| Channels | Website/Facebook/Zalo connection management, health, authorization/revocation and provider webhooks |
| Conversations | scoped Inbox list/detail, members, read state, workflow, notes, tags and human replies |
| Contacts/leads | scoped contact timeline/merge/export and consented Website lead creation |
| Usage/analytics | bounded factual usage, quota and owner/admin operational metrics |
| Widget | published config/session, messages, SSE, images, product-image grants and lead creation |

A documentation refactor must not rename current routes. Provider-specific current paths and protocol constraints are routed through [`refs/channels/README.md`](refs/channels/README.md).

Knowledge replacement routes create a new manual or private-file version and reject unchanged content. Version history is bounded and returns provenance/status metadata rather than source bodies or Storage locations. Review timestamps produce advisory freshness states with a seven-day due-soon window. Retry and rebuild accept a bounded reason and idempotency key and always report that the active generation did not change synchronously. `POST /api/v1/workspaces/{workspace_id}/knowledge/diagnostics` targets selected bases or an Agent assignment, returns only active PostgreSQL-validated sources/chunks, and distinguishes no scope, no ready generation, filtered stale points, no hit and unavailable dependencies.

## SSE contract

Canonical events are `message.start`, `message.delta`, `product.cards`, `source.refs`, `message.completed`, `message.error` and `heartbeat`.

- Use `text/event-stream`, `Cache-Control: no-cache`, disabled proxy buffering and heartbeat comments.
- Persist inbound request identity before generation. Disconnect/cancel records final state and reconciles observed usage.
- Do not stream raw provider prose before final structured-evidence validation.
- Product cards contain server-validated current Catalog facts and safe links/images; source references identify retrieved permitted sources.
- Replay of a completed idempotent Website request must not generate another billable answer.

## Shared channel HTTP/event contract

### Connection management

- Owner/admin creates, verifies, reads health, reauthorizes and revokes a workspace connection.
- Credential submission never echoes tokens, secrets or Vault references.
- Binding validates same-workspace ownership and a usable published Agent revision.
- Revocation disables local processing before best-effort provider cleanup.

### Webhooks

1. Read a strictly bounded raw body required for verification.
2. Verify provider challenge/signature/token before trusting content.
3. Resolve the connection through server-owned provider identity.
4. Persist/deduplicate the provider/connection/event identity.
5. Normalize and persist a message before AI/human processing.
6. Acknowledge within the provider contract; longer work runs durably.

Webhook responses never disclose workspace existence or internal processing details. A provider adapter may parse only the bounded identity needed to locate verification material; no tenant processing occurs before verification.

### Outbound delivery

An outbound request creates or reuses a persisted delivery by idempotency key. Normalized states are `queued | sending | accepted | delivered | failed_retryable | failed_terminal`. Provider acceptance and authenticated delivery are distinct. Lease/fencing prevents stale workers from completing newer claims; retry is bounded and stops when an external effect is ambiguous or already accepted.

Provider response windows, opt-out state, content limits and message classes are rechecked before send. Load the relevant provider reference only when changing that adapter:

- [Facebook Messenger](refs/channels/facebook.md)
- [Zalo OA](refs/channels/zalo.md)

## Inbox, contacts and analytics contracts

- Inbox endpoints provide stable-cursor lists/details, workspace members, per-member read state, assignment, handling mode, workflow status, notes/tags and idempotent human replies.
- Contact endpoints provide scoped list/detail timeline, state/assignment, notes/tags, logical merge/reversal and bounded CSV export. Members remain limited to unassigned/self-assigned records; elevated operations require owner/admin.
- Mutations require CSRF, role checks and optimistic conflict protection or appropriate row locking.
- `GET /api/v1/workspaces/{workspace_id}/analytics` is owner/admin-only, supports bounded day/channel/Agent filters, returns its UTC period/workspace timezone and represents unavailable measures as `null`.
- These responses contain no raw provider details, conversation content or contact PII beyond the authorized purpose.

## Contract evolution

- Prefer additive changes and explicit versioning for breaking payload/event changes.
- Snapshot OpenAPI and regenerate typed frontend clients when the repository workflow requires it.
- Test tenant denial, stable pagination, idempotency mismatch, duplicate webhooks, provider outage, partial stream and cancellation.
- Do not add alias routes for superseded speculative names.

## APPROVED DIRECTION: domain actions

When the first effectful Agent action is approved, expose the owning domain's concrete action rather than a universal arbitrary-tool endpoint. Define server-derived actor/workspace scope, typed validation, authorization, approval if required, idempotency/request hashing, concurrency, durable redacted execution state, safe errors and reconciliation of ambiguous external effects.

This is a design trigger, not a current route family.
