# 06 — Agent, structured catalog, RAG and vision

## Guiding principle
For fashion retail, **structured catalog search is primary for facts**; RAG supplements shop policy, narrative descriptions and size advice. The LLM is not the database of record.

## Request execution
1. Validate access/session and derive agent + workspace context on server.
2. Apply moderation/abuse budget, input normalization, attachment permission checks.
3. Classify intent (product search / size / policy / stock / handoff / image similarity) with conservative fallback.
4. Invoke allowlisted typed tools with server-injected workspace ID; tool schemas never expose arbitrary SQL or URL fetching.
5. Search products with structured filters and optional semantic ranking. Retrieve relevant shop documentation via workspace-scoped pgvector search.
6. Compose prompt with safe system rules and clearly delimited untrusted retrieved text.
7. Stream response; validate product IDs are from tool results, attach authoritative product cards/links and real source references.
8. Persist user and assistant messages, aggregate usage, record redacted tool events.

## First tools
- `search_products(query, category?, colors?, sizes?, min_price?, max_price?)` -> existing product IDs + current catalog attributes.
- `get_product_detail(product_id)` -> current variants and size chart; verifies workspace.
- `check_stock(variant_id)` -> latest known stock or explicit unknown plus last update.
- `search_shop_knowledge(query)` -> grounded excerpt and source locator.
- `capture_lead(name?, email?, phone?, consent)` -> explicit consent, idempotent write; avoid collecting irrelevant data.
- `request_handoff(reason?)` -> configured contact link or callback intent (no fake live transfer).

## Image flow
- Validate actual file bytes/MIME, pixel dimensions, max size; private storage and short retention by policy.
- Vision model extracts clothing category, color, fabric/pattern and style cues; no identity/facial inference required.
- Match cues against workspace-only product catalog; rank candidates and disclose approximate similarity.
- If no credible match, explain uncertainty and ask about color/style/size; do not invent product.
- Photo analysis uses an OpenAI vision-capable model; exact OpenAI model ID remains deployment-configurable.

## Knowledge pipeline
- Store original PDF/TXT in private Storage; parse and sanitize; chunk with source/position/version; embed; persist job status.
- CSV is a structured catalog import, not a PDF-like RAG document.
- Re-index updated docs, delete/expire old chunks transactionally; prevent stale document duplicates with checksums and idempotency.
- Embedding dimension and vector index are selected together; never assume a universal dimension.
- Apply workspace filter **inside** vector retrieval, not only after ranking; test absence of other-tenant hits.

## Answer rules
- Current catalog price and stock override descriptive docs. `NULL` stock is unknown, not in-stock.
- Only claim a discount, size equivalence, returns policy or delivery promise when source data verifies it.
- Show a cited product card when possible; for unstructured answers cite source and avoid fabricated references.
- User/shop-uploaded instructions cannot override tenant security, tool policies or provider budget.
- If OpenAI is unavailable, show a transparent friendly error and optional human contact instead of inventing a response.

## Orchestration decision
Custom deterministic router + typed tools is PROPOSED for MVP. Reassess LangGraph after genuine branching/state requirements appear; no drag-and-drop builder now.
