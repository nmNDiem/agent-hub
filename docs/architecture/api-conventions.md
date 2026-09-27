# API implementation conventions (companion to master API contract)

**Canonical route names/endpoint families and SSE names live in [`../05-api-contract.md`](../05-api-contract.md).** Do not implement old proposed `/shops/*`, `/public/bots/*`, `/auth/me` paths from the independently drafted design package; do not introduce them as aliases. `workspace` is the API tenant and `agent` is the domain entity (chatbot in UI).

## API identity and serialization
- `/api/v1` prefix, JSON/UTF-8; generate stable OpenAPI in FastAPI and typed frontend client from that spec.
- Admin routes authorize workspace membership and capability every time. UUIDv7 `workspace_id` and `public_agent_id` are lowercase unprefixed hyphenated UUID strings. Internal BIGINT IDs for products/documents only inside authenticated workspace-scoped admin APIs; visitor agent/conversation IDs are public UUIDv7 values, never BIGINT.
- `null` means unknown stock/price; do not map to zero. Catalog prices use exact `NUMERIC(18,2)` / application `Decimal`, serialize as decimal strings, and always include explicit ISO currency; timestamps use ISO-8601 UTC.

## Pagination and errors
- List endpoints accept `limit` (default 20, max 100) and opaque cursor; allowlist sort and filter keys; response `{ "items": [], "next_cursor": null }`.
- Error format: `{ "error": { "code": "FORBIDDEN", "message": "...", "request_id": "...", "details": {} } }` with redacted safe messages; use 401 unauth, 403 action denied, 404 existence-hidden tenant resource, 409 state conflict, 413 size, 415 media type, 422 validation, 429 limit and 503 temporary provider fault.
- Idempotency keys scoped to workspace/user or agent/widget session for publish/message/upload creation; database dedupe plus expiry.

## Streaming specifics
Master events: `message.start`, `message.delta`, `product.cards`, `source.refs`, `message.completed`, `message.error`, `heartbeat`. `text/event-stream`, `Cache-Control: no-cache`, disable proxy buffering, heartbeat comments and abort on disconnect. No alternate names `message.products`, `message.sources`, `message.done` unless the master API contract is formally amended.
- Persist incoming message before generation. On failure/cancel record final state and reconcile provider usage. Product cards contain only verified current catalog fields: safe public identifiers/references, approved links/images, effective decimal price, explicit inventory state and relevant generic options/attributes. They must not require fashion-only fields or expose private URLs, dashboard-only internal IDs, raw prompts or sensitive provider errors.
- For cookie-auth admin writes enforce CSRF and correct same-origin forwarding. Widget endpoints derive workspace and agent exclusively from published agent + issued short-lived session; Origin allowlist is defense in depth, not an identity proof.

## Catalog read boundary for agents

- Authorization resolves an `AuthorizedCatalogScope` first; catalog query code never accepts a dashboard `User` and never trusts workspace/location/collection IDs supplied by a model or browser.
- `CatalogQuery` is search intent only. Requested location IDs form a union, requested collection IDs form a union, and location scope intersects collection scope. A request may narrow an authorized scope but cannot widen it.
- The internal read contract is product-centric: `search_products`, `get_product_detail` and `get_variant_availability`. Search limits candidate products before batch hydration; variants, options and location availability are loaded in bounded queries rather than queries inside loops.
- Without a selected location, price is `exact`, `range` or `unknown`; inventory is a count of `in_stock`, `out_of_stock` and `unknown` locations. Never choose an arbitrary location price or sum inventory quantities across locations.
- Per-location availability includes authoritative effective price, nullable quantity, explicit inventory state and `inventory_updated_at`. F3 maps these domain read models to tool output; F4 owns the separate public product-card DTO.
- The authenticated dashboard search route retains its existing optional singular `location_id` and `collection_id` parameters as a compatibility facade. Multi-scope input is introduced only on agent-owned contracts.

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
