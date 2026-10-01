# 05 — API contract (v1)

All paths are prefixed `/api/v1`. Identity, workspace and catalog endpoints are implemented; the remaining endpoint families are proposed until explicitly approved and implemented. See `architecture/api-conventions.md` for payload/error/SSE implementation conventions, and `architecture/identifiers.md` for UUIDv7 vs BIGINT rules. User/workspace IDs are UUIDv7; public agent/conversation IDs are UUIDv7; internal dense records use BIGINT. UI calls agents *chatbots* and workspaces *shops*. Dashboard endpoints require FastAPI-issued auth + server-verified workspace membership/role. Widget endpoints require a short-lived agent/workspace-scoped widget session and abuse control. The `{conversation_public_id}` and `{public_agent_id}` values exposed to visitors are UUIDv7 strings, not internal BIGINTs. Never put privileged service credentials in public JS.

## Identity
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Email/password; creates user and session only, never an implicit workspace |
| POST | `/auth/login` | Issues short-lived access token + rotating refresh session |
| POST | `/auth/refresh` | Rotation; detect reuse |
| POST | `/auth/logout` | Revoke refresh session |
| POST | `/auth/verify-email` | One-time code/token |
| POST | `/auth/forgot-password` | Non-enumerating response |
| POST | `/auth/reset-password` | One-time expiring token; revoke sessions |
| GET | `/me` | Signed-in profile + memberships |

### Browser session contract

The backend uses FastAPI-issued `agenthub_access` and `agenthub_refresh` HttpOnly cookies. The readable `agenthub_csrf` cookie must be echoed in `X-CSRF-Token` for authenticated unsafe requests. Access cookies last 15 minutes and refresh sessions last 14 days by default; both values are server configuration. Refresh rotation invalidates the previous token and replay revokes the remaining token family. The access token is never stored in browser storage.

Registration creates the user and session but does not silently create a workspace. A user with no memberships creates the first workspace through `POST /workspaces`; the workspace and `owner` membership are committed atomically. Email verification/recovery routes exist only when a real delivery adapter is configured.

## Owner / workspace
| Method | Path | Notes |
|---|---|---|
| GET/POST | `/workspaces` | List memberships / create workspace |
| GET/PATCH | `/workspaces/{workspace_id}` | Membership and role enforced |
| GET/POST | `/workspaces/{workspace_id}/agents` | List/create draft agents; owner/admin create, members may read |
| GET/PATCH | `/workspaces/{workspace_id}/agents/{public_agent_id}` | Read/update validated core configuration; F3.1 does not expose status transitions |
| PUT | `/workspaces/{workspace_id}/agents/{public_agent_id}/catalog-scope` | Atomically replace allowed location/collection scope; `null` means all, `[]` means none |
| POST | `/workspaces/{workspace_id}/agents/{public_agent_id}/publish` | Future F4 route; requires complete configuration and an immutable revision |
| GET/PUT | `/workspaces/{workspace_id}/agents/{public_agent_id}/widget` | Future F4 branding + domain allowlist + embed snippet |
| CRUD | `/workspaces/{workspace_id}/products` | Filtering, pagination, validation |
| CRUD | `/workspaces/{workspace_id}/products/{product_id}/variants` | SKU, generic options, legacy color/size compatibility, price and stock |
| PUT/DELETE | `/workspaces/{workspace_id}/products/{product_id}/size-guide` | Optional validated JSON guide |
| POST/GET/DELETE | `/workspaces/{workspace_id}/products/{product_id}/images` | Private upload, authorized signed URL and cleanup state |
| POST | `/workspaces/{workspace_id}/catalog/import/preview` | Validate UTF-8 CSV without writes |
| POST | `/workspaces/{workspace_id}/catalog/import` | Revalidate and transactionally import CSV; requires preview hash and `Idempotency-Key` |
| POST | `/workspaces/{workspace_id}/catalog/imports` | Upload and analyze CSV/XLS/XLSX into persisted staging; no catalog mutation |
| GET | `/workspaces/{workspace_id}/catalog/imports/{import_id}` | Read workspace-scoped status, diff and issues |
| POST | `/workspaces/{workspace_id}/catalog/imports/{import_id}/issues/{issue_id}/resolve` | Resolve a persisted ambiguity |
| POST | `/workspaces/{workspace_id}/catalog/imports/{import_id}/commit` | Atomic, idempotent MERGE commit; requires `Idempotency-Key` |
| GET | `/workspaces/{workspace_id}/catalog/search` | Structured text/brand/price/stock/options/attributes search |
| GET/POST | `/workspaces/{workspace_id}/knowledge-bases` | Cursor list/create; members read, owner/admin create |
| PATCH/DELETE | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}` | Owner/admin update or archive; archive cancels active jobs and prevents cutover |
| GET/PUT | `/workspaces/{workspace_id}/agents/{public_agent_id}/knowledge-bases` | Read or atomically replace workspace-scoped assignments |
| GET | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}/documents` | Cursor list active sources and their latest ingestion state |
| POST | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}/documents/text` | Idempotent manual profile/FAQ/policy/size-guidance source |
| POST | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}/documents` | Streaming PDF/TXT upload with MIME/signature, quota and rate validation |
| DELETE | `/workspaces/{workspace_id}/knowledge-bases/{kb_id}/documents/{document_id}` | Revoke source first; cancel jobs and schedule derived-data cleanup |
| GET | `/workspaces/{workspace_id}/ingestion-jobs/{job_id}` | Workspace-scoped status and safe error code |
| POST | `/workspaces/{workspace_id}/ingestion-jobs/{job_id}/retry` | Owner/admin retry only for classified transient failures |
| GET | `/workspaces/{workspace_id}/conversations` | Pagination and redacted export policy |
| GET | `/workspaces/{workspace_id}/leads` | PII accessible only to roles allowed |
| GET | `/workspaces/{workspace_id}/usage` | Proposed internal usage, not billing |
| GET | `/workspaces/{workspace_id}/dashboard` | Proposed real KPIs/time-series; never return mock metrics as real data |
| GET | `/workspaces/{workspace_id}/conversations/{conversation_public_id}` | Proposed authorized conversation transcript |
| POST | `/workspaces/{workspace_id}/agents/{public_agent_id}/playground/messages:stream` | Implemented authenticated draft preview via the grounded runtime; CSRF and membership required |

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

The dashboard Playground request is `{ "message": string, "history": [{ "role": "user" | "assistant", "content": string }] }`. History is bounded, treated as untrusted context and not persisted as a shopper conversation. The server completes the guarded runtime before emitting validated channel-neutral text deltas, then emits authoritative `product.cards` and validated `source.refs`; it never forwards raw provider output before final reference, claim and safety validation. Future channel adapters render the same structured result according to channel capabilities rather than changing the core answer contract. `message.error` carries a safe `{code, message, retryable}` payload. If OpenAI generation or Qdrant is not configured, the endpoint fails before opening the stream with `503 AGENT_RUNTIME_DISABLED`.

## Error envelope proposal
`{ "error": { "code": "NOT_FOUND", "message": "...", "request_id": "..." } }`.
Use non-leaking 404 for unauthorized cross-tenant resource where appropriate, 401 for missing auth, 403 for forbidden action, 422 for input validation, 429 for quota/rate limit, 503 for temporary model/provider failures. Define pagination and concurrency/timeout behavior before client integration.

### Catalog contract

Product lists use opaque cursor pagination ordered by `(created_at DESC, id DESC)`. Product and variant IDs are internal BIGINT values exposed only behind authenticated, workspace-scoped dashboard routes. Owner/admin may mutate catalog data; members have read access. `DELETE` archives products and variants, and archived SKU values remain reserved. Prices serialize as exact decimal strings; `null` and zero remain distinct for product prices, variant overrides and stock.

The legacy CSV facade accepts columns `product_sku,name,description,category,currency,price,product_url,variant_sku,variant_name,color,size,variant_price,stock_quantity`. It remains backward-compatible, but adapts into the universal import pipeline; it is not a second importer or the canonical contract for new clients.

Catalog images accept verified PNG/JPEG/WebP only and are stored privately. Metadata, upload, signed URL and cleanup endpoints all enforce backend membership and immutable workspace scope. Deletion first commits `cleanup_pending`, then attempts Storage deletion; failure returns the persisted pending status and can be retried through `POST .../images/{image_id}/cleanup` without claiming the database transaction rolled back.

New clients use the import-job routes. The universal importer detects structure rather than vendor, accepts CSV/XLS/XLSX, preserves missing/blank/explicit-null/value states, persists normalized staging and issues, previews create/update/unchanged/conflict outcomes, and never treats a record absent from a file as deletion. Commit revalidates affected identities and applies an atomic idempotent MERGE. Trusted external references and confirmed mapping profiles may establish identity; names and AI guesses may not. Multiple `option=Name:Value` filters on catalog search are correlated to the same actual variant. Search/read contracts expose generic options and attributes while retaining legacy color/size response fields during compatibility.

F2.2 adds authenticated workspace routes for locations, location variants/inventory/price overrides and catalog collections. Location and collection IDs are always resolved inside the authorized workspace. `GET .../catalog/search` retains optional singular `location_id` and `collection_id` parameters for dashboard compatibility; effective price is location override, then variant override, then product price. Search stock comes only from `inventory_levels`. Universal imports may map an explicit `location_code`; unknown codes are validation errors and never create locations implicitly. Agents and agent assignments are not part of this contract until F3.

F3 uses an internal product-centric catalog contract rather than the dashboard `User` DTO: a trusted authorization resolver produces workspace plus allowed location/collection IDs, then a separate query may only narrow that scope. Multiple locations are unioned, multiple collections are unioned, and the two dimensions intersect. No-location results expose exact/range/unknown price and counts for in-stock/out-of-stock/unknown availability; only the detail availability contract exposes per-location quantity, effective price and freshness. F3 owns the tool mapper and F4 owns the public product-card DTO.

F3.1 implements `search_products`, `get_product_detail` and `check_stock` as internal typed tools, not browser endpoints. They accept only an immutable server-resolved `AuthorizedCatalogScope`, expose generic options/attributes and authoritative price/inventory facts, and use color/size only as compatibility projections. Images are returned as opaque catalog image IDs plus safe metadata; Storage object keys, signed URLs and recorded remote URLs are never part of tool output. F4 owns the separately authorized public image-delivery policy.

F3.2 knowledge resources use authenticated dashboard BIGINT IDs only after membership resolution; they are never public widget identifiers. Cross-workspace access returns non-leaking `404`, while a same-workspace member attempting a mutation receives `403`. Document creation requires `Idempotency-Key`. Jobs expose `awaiting_profile`, `queued`, `processing`, `retry_scheduled`, `succeeded`, `failed` or `cancelled`; only provider/storage/network-class transient failures retry automatically. Corrupt, encrypted, image-only or limit-exceeding PDFs return stable permanent error codes. Raw document text, file contents, Storage keys and parser tracebacks are not returned.
