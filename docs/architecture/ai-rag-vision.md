# AI pipeline, retrieval and vision

## Single flow for Playground and Web
1. Authenticate owner / validate published widget + session and limits; resolve bot revision and `workspace_id`.
2. Normalize question, attachments and locale; persist message idempotently.
3. Route deterministic intents: exact SKU/external reference, product availability, generic option/attribute filters, shipping/returns/size policies; use the F2.1 workspace-scoped structured catalog search for products/variants. Multiple option constraints must match the same actual variant. Unknown stock/price stays unknown. No fabricated order lookup.
4. Retrieve relevant shop-scoped knowledge chunks where document status `ready` AND bot revision permits source. Rank by vector similarity and optional keyword; use document, source ID, chunk position and freshness as metadata. Limit context size.
5. Build server-side instruction layers: platform safety, bot published style, shop-specific verified context, recent conversation, visitor message. Treat uploaded docs, website text, image labels and user messages as **untrusted data**, not instructions.
6. Call configured OpenAI model with server-side API key, bounded output, timeout and retry budget; stream text. Image input only with a model verified to support vision. Avoid relying on volatile model names in UI.
7. Validate structured product/variant IDs, links and safe image references; ensure all matches belong to the workspace and are permissible. Resolve effective price and inventory from current catalog records rather than model text; citations only for actually retrieved chunk IDs. Persist messages, usage, elapsed time, errors and source refs.
8. Return structured data and text separately; do not scrape model prose for commerce actions.

## OpenAI adapter
`ModelGateway.generate_stream(messages, images, tools, config) -> async events`; `EmbeddingGateway.embed(texts) -> vectors`. Version-pin SDK and selected model names in server configuration; unit-test capabilities (vision, streaming, output schema), dimensions and pricing externally before rollout. Protect against provider retry storm; capped tokens/turn, tokens/shop/day, per-bot concurrency, and request timeout. Dashboard usage shows recorded measurements only.

## Embeddings and isolation
Persist embedding metadata `{model, dimension, content_hash}` and re-index when any change; never compare embeddings from incompatible dimensions/models. For baseline use one model consistently; decide vector dimension from actual model. Retrieval query MUST contain tenant filter, allowed document filters and `ready` check before returned context; test with similar text in two workspaces to prove isolation. Retrieval source score does not imply truth. If none retrieved, respond based on only authorized available data with an appropriate uncertainty statement.

## Fashion-specific rules
- `Color` and `Size` are ordinary generic option definitions, not hardcoded catalog columns. Recommending `size M` requires a matching option on the returned variant or actual size-chart evidence; do not assert a garment fits the person from photo alone.
- Stock availability is stated only from known current structured stock or explicit `availability` data; stale stock is qualified.
- Image may be used for general item/color/style identification, not for sensitive inferences about the person. Discard image metadata where not needed; don't include private photo in logs.
- Do not infer that a product exists merely because document text mentions it; use catalog lookup.

## Testing
Offline unit tests with fake model gateway for exact pipeline; one opt-in provider integration smoke test behind env flag, with low cost ceilings. Cases: no knowledge, conflicting FAQ, prompt injection in PDF, cross-tenant similarly named product, two option filters that only different variants satisfy, product without variants/options, unknown versus zero stock, effective-price fallback, unavailable variant, unsafe/remote image reference, corrupt visitor image, disconnected SSE, retry/idempotency, malformed tool output and source no longer permitted.
