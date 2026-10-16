# API and event contracts

FastAPI publishes the executable OpenAPI contract. This document owns stable cross-cutting conventions and route families; do not duplicate full generated request/response schemas here.

All route families below are **CURRENT** unless explicitly labeled otherwise. AgentHub has no generic capability-registration or effectful-agent-action API today.

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
| Conversations | role-scoped inbox list/detail, members, read state, workflow, notes, tags and human replies |
| Leads | owner/admin list/status/export and public consented Website creation |
| Dashboard/usage | bounded aggregates, observed usage and workspace monthly quota |
| Analytics | owner/admin 7/30-day operational metrics with channel and agent filters |
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

The Facebook first-slice routes are:

- `GET|POST /api/v1/workspaces/{workspace_id}/channels/facebook` for owner/admin-safe listing
  and Page connection;
- `POST /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}/health` for token
  validation and Page webhook subscription repair;
- `POST /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}/reauthorize` for
  same-Page Vault credential rotation;
- `DELETE /api/v1/workspaces/{workspace_id}/channels/facebook/{connection_id}` for local-first
  revocation;
- `GET|POST /api/v1/webhooks/facebook` for Meta challenge and signed delivery.

Connection responses expose Page identity, agent binding, lifecycle/health timestamps and latest
safe queue/delivery state, never the Page token or Vault reference. The POST webhook supports
authenticated text/image/unsupported-attachment metadata and `delivery.mids` events, persists
response work before acknowledgement and acknowledges unknown/revoked Pages without exposing
tenant state.

The Zalo routes are:

- `GET /api/v1/workspaces/{workspace_id}/channels/zalo` for scoped connection status;
- `POST /api/v1/workspaces/{workspace_id}/channels/zalo/oauth/start` for a PKCE authorization URL;
- `GET /api/v1/channels/zalo/oauth/callback` for the single-use, authenticated OAuth callback;
- `PUT /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}/webhook-secret` for the
  separate write-only OA signing secret;
- `POST /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}/health` and
  `DELETE /api/v1/workspaces/{workspace_id}/channels/zalo/{connection_id}` for verification and
  local revocation;
- `POST /api/v1/webhooks/zalo` for signed OA events.

The OAuth start response contains only the Zalo authorization URL and expiry. Callback state is
hashed at rest, expires after ten minutes and is consumed before provider exchange. Callback
redirects use the configured AgentHub origin and fixed chatbot path. Connection responses expose
neither tokens, OA secret nor Vault references.

### Webhooks

1. Read a strictly bounded raw body required for provider verification.
2. Verify challenge/signature/token before trusting payload contents.
3. Resolve the connection using server-owned provider identity.
4. Persist/dedupe `(provider, connection_id, external_event_id)`.
5. Normalize and persist a message before AI/human processing.
6. Return provider-required acknowledgement within its verified timing contract; longer work runs durably.

Webhook responses never expose workspace existence or internal processing details.

Zalo is the provider-specific exception to step 2's lookup ordering: the adapter may parse only
the bounded app/OA identity needed to find the server-owned candidate connection and its OA secret.
It then verifies `X-ZEvent-Signature` before normalization, persistence or tenant processing.

### Outbound delivery

An outbound request creates/reuses a persisted delivery by idempotency key. Delivery exposes
normalized `queued | sending | accepted | delivered | failed_retryable | failed_terminal` state
and safe provider error classification. `accepted` means the provider returned a message ID;
`delivered` requires an authenticated provider receipt. Retries are bounded and never repeat a
terminally accepted provider message.

Delivery claims use a short lease and fencing token. A stale runner cannot complete or fail a
newer claim, and a lease abandoned on the final allowed attempt becomes terminal rather than
remaining indefinitely in `sending`.

Facebook sends `POST /{page-id}/messages` with a server-resolved Page token, a connection-scoped
PSID recipient, `messaging_type=RESPONSE` and text only. Definite rate-limit/transient rejections
may retry. Timeout, transport, malformed success and HTTP 5xx outcomes are terminal
`FACEBOOK_DELIVERY_UNKNOWN`: their external side effect is ambiguous and automatic replay could
duplicate a customer reply.

The adapter rejects generation completion and send outside 24 hours from the latest inbound
message or while the thread is opted out. M1.2 has no message-tag, marketing or proactive-send
contract.

Zalo sends `POST https://openapi.zalo.me/v3.0/oa/message/cs` with a refreshed server-resolved
access token, connection-scoped user ID and text of at most 2,000 characters. The shared worker
enforces the 48-hour reply window and opt-out state before calling the adapter. Authentication
rejections require OAuth reconnect; definite rate-limit/transient errors retry with the shared
bounded policy, while ambiguous delivery results are terminal.

### Inbox and contacts

M1.4 authenticated APIs provide stable-cursor conversation lists/details, current workspace
members, per-member read state, assignment, handling mode, workflow status, notes/tags and
idempotent human replies. Each write uses CSRF, role checks, optimistic state conflict protection
and workspace-safe IDs. Delivery responses expose safe queue/error metadata; ambiguous outcomes
are not replayed automatically.

Authenticated contact APIs under `/api/v1/workspaces/{workspace_id}/contacts` provide a
stable-cursor list, detail timeline, state/assignment updates, notes, shared tags, logical merges,
merge reversal and bounded CSV export. Every lookup resolves the authenticated workspace
membership; members are limited to unassigned/self-assigned contacts and may claim an unassigned
contact, while export, duplicate suggestions and merge operations require owner/admin. Mutations
require CSRF and state-changing contact/merge operations use optimistic versions or row locks.

### Operational analytics

`GET /api/v1/workspaces/{workspace_id}/analytics` is owner/admin-only and accepts `days=7|30`, an
optional `channel=web|facebook|zalo` and an optional workspace-scoped `agent_public_id`. It returns
the explicit UTC period plus workspace timezone, activity series, channel/agent breakdowns,
measured response samples, AI/human resolution, consented lead conversion, delivery outcomes and
top product-card impressions. Unavailable timings, conversion denominators and Website provider
delivery states remain `null`; the response contains no conversation text, contact PII or raw
provider details.

## Contract evolution

- Prefer additive changes and explicit versioning for breaking channel payloads/events.
- Snapshot OpenAPI and regenerate typed frontend clients.
- Test tenant denial, pagination stability, idempotency mismatch, duplicate webhook, provider outage, partial stream and cancelled request.
- Do not add alias routes for superseded speculative names.

## APPROVED DIRECTION: domain actions

When the first effectful Agent action is approved, expose the owning domain's concrete action rather than a universal arbitrary-tool endpoint. Its contract must define server-derived actor/workspace scope, typed validation, authorization, approval if required, idempotency/request hashing, concurrency, durable redacted execution state, safe errors, and reconciliation of ambiguous external effects.

This section is a design gate, not a current route family.
