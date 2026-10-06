# API and event contracts

FastAPI publishes the executable OpenAPI contract. This document owns stable cross-cutting conventions and route families; do not duplicate full generated request/response schemas here.

## General conventions

- API prefix: `/api/v1`; JSON/UTF-8; ISO-8601 UTC timestamps.
- Authenticated dashboard routes use FastAPI cookies, CSRF protection for unsafe methods and server-verified workspace membership/capability.
- Public channel routes derive tenant/agent/conversation scope from an opaque session or verified channel connection, never request tenant fields.
- Prices serialize as exact decimal strings with ISO currency. `null` remains unknown and is not converted to zero.
- Lists use opaque cursor pagination: `{"items": [], "next_cursor": null}` with bounded `limit` and allowlisted filters/sorts.
- Errors use `{"error":{"code":"...","message":"...","request_id":"...","details":{}}}` with safe details.
- Use 401 missing/invalid authentication, 403 denied action, non-leaking 404 for hidden tenant resources, 409 state conflict, 413 size, 415 media, 422 validation, 429 limit and 503 dependency unavailable.
- Idempotency keys are scoped to authenticated actor/workspace or public session/connection and validated against a request hash.

## Current route families

| Family | Main operations |
|---|---|
| Health | `/health`, `/health/live`, `/health/ready` |
| Auth | register, login, refresh, logout, verify, forgot/reset password, `/me` |
| Workspaces | list/create/read/update workspace and current membership context |
| Agents | CRUD config, catalog/knowledge assignments, publish, pause, Web configuration and Playground stream |
| Catalog | products/variants/size guides/images, locations, collections, import jobs/issues/commit and structured search |
| Knowledge | bases, documents, ingestion jobs, retry/archive and assignments |
| Conversations | owner/admin stable-cursor list and redacted detail |
| Leads | owner/admin list/status/export and public consented Website creation |
| Dashboard/usage | bounded aggregates, observed usage and workspace monthly quota |
| Widget | published config/session, conversation/messages, SSE replay, image upload/delete, product-image grant and lead creation |

Exact current paths remain defined by generated OpenAPI and existing clients. A documentation refactor must not rename routes.

## SSE contract

Canonical events:

`message.start`, `message.delta`, `product.cards`, `source.refs`, `message.completed`, `message.error`, `heartbeat`.

- Use `text/event-stream`, `Cache-Control: no-cache`, proxy buffering disabled and heartbeat comments.
- Persist incoming identity before generation. Disconnect/cancel records final state and reconciles observed usage.
- Do not stream raw provider prose before final structured evidence validation.
- Product cards contain server-validated current catalog facts and safe links/images; source references identify actually retrieved permitted sources.
- Replay of a completed idempotent Website request must not regenerate a billable answer.

## M1 channel HTTP/events

Provider route names are finalized in each approved task, but every adapter follows these contracts:

The M1.1 foundation adds no public provider route. Provider tasks verify their bounded raw
request first, then pass a typed verified envelope into the shared channel service. Website
HTTP and SSE routes remain unchanged.

### Connection management

- Owner/admin creates, verifies, reads health, reauthorizes and revokes a workspace channel connection.
- Credential submission responses never echo tokens.
- Connection-to-agent binding validates same-workspace ownership and a usable published agent revision.

### Webhooks

1. Read a strictly bounded raw body required for provider verification.
2. Verify challenge/signature/token before trusting payload contents.
3. Resolve the connection using server-owned provider identity.
4. Persist/dedupe `(provider, connection_id, external_event_id)`.
5. Normalize and persist a message before AI/human processing.
6. Return provider-required acknowledgement within its verified timing contract; longer work runs durably.

Webhook responses never expose workspace existence or internal processing details.

### Outbound delivery

An outbound request creates/reuses a persisted delivery by idempotency key. Delivery exposes normalized `queued | sending | delivered | failed_retryable | failed_terminal` state and safe provider error classification. Retries are bounded and never repeat a terminally accepted provider message.

Delivery claims use a short lease and fencing token. A stale runner cannot complete or fail a
newer claim, and a lease abandoned on the final allowed attempt becomes terminal rather than
remaining indefinitely in `sending`.

### Inbox and contacts

M1 authenticated APIs provide stable-cursor conversation lists/details, send/retry, assignment, handling mode, status, notes/tags and contact timeline operations. Each write uses CSRF, role/capability checks, current-state conflict protection and workspace-safe IDs. API specifics belong in the active task before implementation.

## Contract evolution

- Prefer additive changes and explicit versioning for breaking channel payloads/events.
- Snapshot OpenAPI and regenerate typed frontend clients.
- Test tenant denial, pagination stability, idempotency mismatch, duplicate webhook, provider outage, partial stream and cancelled request.
- Do not add alias routes for superseded speculative names.
