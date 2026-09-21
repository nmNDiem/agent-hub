# 05 — Proposed API contract (v1 draft)

All paths are prefixed `/api/v1`. See `architecture/api-conventions.md` for payload/error/SSE implementation conventions, and `architecture/identifiers.md` for UUIDv7 vs BIGINT rules. User/workspace IDs are UUIDv7; public agent/conversation IDs are UUIDv7; internal dense records use BIGINT. UI calls agents *chatbots* and workspaces *shops*. Versioning, exact payload shapes and status codes to be locked in OpenAPI during implementation. Dashboard endpoints require FastAPI-issued auth + server-verified workspace membership/role. Widget endpoints require a short-lived agent/workspace-scoped widget session and abuse control. The `{conversation_public_id}` and `{public_agent_id}` values exposed to visitors are UUIDv7 strings, not internal BIGINTs. Never put privileged service credentials in public JS.

## Identity
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Email/password; create owner workspace or scoped invitation acceptance |
| POST | `/auth/login` | Issues short-lived access token + rotating refresh session |
| POST | `/auth/refresh` | Rotation; detect reuse |
| POST | `/auth/logout` | Revoke refresh session |
| POST | `/auth/verify-email` | One-time code/token |
| POST | `/auth/forgot-password` | Non-enumerating response |
| POST | `/auth/reset-password` | One-time expiring token; revoke sessions |
| GET | `/me` | Signed-in profile + memberships |

### F1 browser session contract

F1 uses FastAPI-issued `agenthub_access` and `agenthub_refresh` HttpOnly cookies. The readable `agenthub_csrf` cookie must be echoed in `X-CSRF-Token` for authenticated unsafe requests. Access cookies last 15 minutes and refresh sessions last 14 days by default; both values are server configuration. Refresh rotation invalidates the previous token and replay revokes the remaining token family. The access token is never stored in browser storage.

Registration creates the user and session but does not silently create a workspace. A user with no memberships creates the first workspace through `POST /workspaces`; the workspace and `owner` membership are committed atomically. Email verification/recovery routes exist only when a real delivery adapter is configured.

## Owner / workspace
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/workspaces` | List memberships / create workspace |
| GET/PATCH | `/workspaces/{workspace_id}` | Membership and role enforced |
| GET/POST/PATCH | `/workspaces/{workspace_id}/agents` | List, create, update; check status transitions |
| POST | `/workspaces/{workspace_id}/agents/{agent_id}/publish` | Requires complete configuration |
| GET/PUT | `/workspaces/{workspace_id}/agents/{agent_id}/widget` | Branding + domain allowlist + embed snippet |
| CRUD | `/workspaces/{workspace_id}/products` | Filtering, pagination, validation |
| CRUD | `/workspaces/{workspace_id}/products/{product_id}/variants` | SKU, color, size, stock |
| POST | `/workspaces/{workspace_id}/catalog/import` | CSV validation; idempotent import job |
| CRUD | `/workspaces/{workspace_id}/knowledge-bases` | Knowledge grouping |
| POST | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}/documents` | Server-validated file upload |
| GET | `/workspaces/{workspace_id}/ingestion-jobs/{job_id}` | Per-tenant status |
| GET | `/workspaces/{workspace_id}/conversations` | Pagination and redacted export policy |
| GET | `/workspaces/{workspace_id}/leads` | PII accessible only to roles allowed |
| GET | `/workspaces/{workspace_id}/usage` | Internal usage, not billing; F5 |
| GET | `/workspaces/{workspace_id}/dashboard` | Real KPIs/time-series; F5, not F0 mock metrics |
| GET | `/workspaces/{workspace_id}/conversations/{conversation_public_id}` | Authorized conversation transcript; F5 |
| POST | `/workspaces/{workspace_id}/agents/{public_agent_id}/playground/messages:stream` | Draft preview via same generation service, scoped and metered; F3 |

## Widget / visitor
| Method | Path | Notes |
|---|---|---|
| POST | `/widget/{public_agent_id}/sessions` | Check agent published, origin policy, abuse limits; issue scoped opaque session token |
| POST | `/widget/conversations` | Scope derived from widget token, not request workspace ID |
| GET | `/widget/conversations/{conversation_public_id}/messages` | Only matching visitor session |
| POST | `/widget/conversations/{conversation_public_id}/messages` | User text + optional validated attachment refs |
| GET | `/widget/conversations/{conversation_public_id}/stream` | SSE; authorized for conversation, not shared tenant stream |
| POST | `/widget/uploads/images` | Validate content and quota, return scoped attachment handle |
| POST | `/widget/conversations/{conversation_public_id}/leads` | Explicit visitor consent |

## SSE example event taxonomy
`message.start`, `message.delta`, `product.cards`, `source.refs`, `message.completed`, `message.error`, `heartbeat`. Stable event IDs if replay is implemented. Terminate streaming on session expiry, disconnect, exhausted budget or denied tool access. Avoid logging token deltas of personal content.

## Error envelope proposal
`{ "error": { "code": "NOT_FOUND", "message": "...", "request_id": "..." } }`.
Use non-leaking 404 for unauthorized cross-tenant resource where appropriate, 401 for missing auth, 403 for forbidden action, 422 for input validation, 429 for quota/rate limit, 503 for temporary model/provider failures. Define pagination and concurrency/timeout behavior before client integration.
