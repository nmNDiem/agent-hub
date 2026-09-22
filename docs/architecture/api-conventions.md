# API implementation conventions (companion to master API contract)

**Canonical route names/endpoint families and SSE names live in [`../05-api-contract.md`](../05-api-contract.md).** Do not implement old proposed `/shops/*`, `/public/bots/*`, `/auth/me` paths from the independently drafted design package; do not introduce them as aliases. `workspace` is the API tenant and `agent` is the domain entity (chatbot in UI).

## API identity and serialization
- `/api/v1` prefix, JSON/UTF-8; generate stable OpenAPI in FastAPI and typed frontend client from that spec.
- Admin routes authorize workspace membership and capability every time. UUIDv7 `workspace_id` and `public_agent_id` are lowercase unprefixed hyphenated UUID strings. Internal BIGINT IDs for products/documents only inside authenticated workspace-scoped admin APIs; visitor agent/conversation IDs are public UUIDv7 values, never BIGINT.
- `null` means unknown stock/price; do not map to zero. F2 prices use exact `NUMERIC(18,2)` / application `Decimal`, serialize as decimal strings, and always include explicit ISO currency; timestamps use ISO-8601 UTC.

## Pagination and errors
- List endpoints accept `limit` (default 20, max 100) and opaque cursor; allowlist sort and filter keys; response `{ "items": [], "next_cursor": null }`.
- Error format: `{ "error": { "code": "FORBIDDEN", "message": "...", "request_id": "...", "details": {} } }` with redacted safe messages; use 401 unauth, 403 action denied, 404 existence-hidden tenant resource, 409 state conflict, 413 size, 415 media type, 422 validation, 429 limit and 503 temporary provider fault.
- Idempotency keys scoped to workspace/user or agent/widget session for publish/message/upload creation; database dedupe plus expiry.

## Streaming specifics
Master events: `message.start`, `message.delta`, `product.cards`, `source.refs`, `message.completed`, `message.error`, `heartbeat`. `text/event-stream`, `Cache-Control: no-cache`, disable proxy buffering, heartbeat comments and abort on disconnect. No alternate names `message.products`, `message.sources`, `message.done` unless the master API contract is formally amended.
- Persist incoming message before generation. On failure/cancel record final state, reconcile provider usage. Product cards contain only verified catalog fields and approved links; do not expose private URLs, internal IDs, raw prompts or sensitive provider errors.
- For cookie-auth admin writes enforce CSRF and correct same-origin forwarding. Widget endpoints derive workspace and agent exclusively from published agent + issued short-lived session; Origin allowlist is defense in depth, not an identity proof.

## Request examples
```json
{
  "public_id": "<generated-uuidv7>",
  "workspace_id": "<generated-uuidv7>",
  "name": "Tư vấn thời trang",
  "draft_config": {"language": "vi", "sources": {"catalog": true}},
  "published_revision": null
}
```
Placeholders are illustrations, not fixture values; tests generate valid UUIDv7.
