# 20 — Full-system API and event design (future modules)

## Versioning principles
FastAPI publishes OpenAPI; route family `/api/v1`. Keep stable error envelope, idempotency for writes/retries, cursor pagination for ordered data, UTC timestamps, client-safe public IDs and explicit workspace resource scope. The existing MVP endpoint outline is `docs/05-api-contract.md`; examples below are **planned**, not implemented.

## Planned route families
| Domain | Example operations | Availability |
|---|---|---|
| Auth | register/login/refresh/logout/reset/verify | MVP |
| Workspaces | memberships/roles/invitations/settings | MVP core; invites later |
| Agents | CRUD/revisions/publish/pause/evaluations | MVP core; revisions later |
| Catalog | product/variant/size chart/import/sync status | MVP CRUD/import; connectors later |
| Knowledge | upload/source/index status/search provenance | MVP basic; URL sync later |
| Widget | public config/session/message/image upload | MVP |
| Conversations | thread/messages/leads/handoff | MVP history/lead; inbox later |
| Channels | connect/disconnect/webhook/delivery | Future |
| Billing | plan/entitlement/usage/invoice/webhook | Usage MVP; charges future |
| Operations | jobs/audit/retention/exports | Minimal MVP; richer future |

## Events
Persist a domain event/outbox for significant durable state transitions once asynchronous integrations are introduced: `knowledge.ingestion.requested/completed/failed`, `agent.published/paused`, `message.received`, `message.delivery.failed`, `lead.created`, `subscription.updated`, `tenant.deletion.requested`. Include event ID/version, workspace_id, resource ID, occurred_at, correlation_id, retry count; do not embed raw message content/credentials in routine events.

## HTTP/stream contract
SSE stream events include typed `message.delta`, `message.completed`, `product.cards`, `source.references`, `usage`, `error` with well-defined ordering and finalization. Model-specific payloads do not leak into public API. Reconnection must not silently regenerate billable answers. Channel adapters consume the normalized response and render supported subset.

## Contract evolution tests
Snapshot OpenAPI and client types; check backward-compatible additive changes; test authorization and 404/403 behavior, tenant filtering, zero-data cases, retry dedupe, provider outage, partial model response and cancelled streams before publishing a breaking change.
