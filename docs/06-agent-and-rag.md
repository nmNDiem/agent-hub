# 06 — Agent, structured catalog, RAG and vision

## Guiding principle
For fashion retail, **structured catalog search is primary for facts**; RAG supplements shop policy, narrative descriptions and size advice. The LLM is not the database of record.

## Request execution
1. Validate access/session and derive agent + workspace context on server.
2. Apply moderation/abuse budget, input normalization, attachment permission checks.
3. Classify intent (product search / size / policy / stock / handoff / image similarity) with conservative fallback.
4. Invoke allowlisted typed tools with server-injected workspace ID; tool schemas never expose arbitrary SQL or URL fetching.
5. Search products with workspace-scoped structured filters over canonical catalog fields, generic options and attributes, then optionally apply semantic ranking. Retrieve relevant shop documentation through Qdrant with a server-injected workspace filter and active embedding profile.
6. Compose prompt with safe system rules and clearly delimited untrusted retrieved text.
7. Stream response; validate product IDs are from tool results, attach authoritative product cards/links and real source references.
8. Persist user and assistant messages, aggregate usage, record redacted tool events.

## First tools
- `search_products(query, category?, options?, attributes?, min_price?, max_price?, in_stock?)` -> existing product IDs and matching variant IDs with current structured facts. Every requested option must match the same actual variant; `color`/`size` inputs, if retained, adapt to generic options.
- `get_product_detail(product_id)` -> current variants, generic options/attributes, safe image references and optional size chart; verifies workspace.
- `check_stock(variant_id)` -> latest known quantity/inventory policy or explicit unknown plus last update.
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
- Store original PDF/TXT in private Storage; parse and sanitize; chunk with source/position/version; embed through `EmbeddingProvider`; index through `KnowledgeVectorIndex`; persist job and index status in Postgres.
- CSV/XLS/XLSX catalog files use the universal structured importer, not the knowledge/RAG ingestion path.
- Re-index updated docs, delete/expire old chunks transactionally; prevent stale document duplicates with checksums and idempotency.
- Persist immutable embedding profiles containing provider, model, dimensions, provider revision, pipeline version and distance metric. Never infer dimension from a model string or compare vectors from different profiles.
- Treat Qdrant as a rebuildable derived index. Apply workspace and allowed-source filters **inside** vector retrieval, then revalidate returned chunks against the active ready generation in Postgres; test absence of other-tenant hits.

## Answer rules
- Current effective catalog price (location override, otherwise variant override, otherwise product price) and location-scoped structured inventory override descriptive docs. `NULL` stock is unknown, not in-stock, while zero is known out of stock. F3 resolves allowed agent locations/collections before calling the F2.2 scoped search contract.
- Tool and card outputs use generic option/attribute labels. F3/F4 must not assume every catalog has `color`, `size`, variants or a size guide.
- Only claim a discount, size equivalence, returns policy or delivery promise when source data verifies it.
- Show a cited product card when possible; for unstructured answers cite source and avoid fabricated references.
- User/shop-uploaded instructions cannot override tenant security, tool policies or provider budget.
- If OpenAI is unavailable, show a transparent friendly error and optional human contact instead of inventing a response.

## Orchestration decision
Custom deterministic router + typed tools is PROPOSED for MVP. Reassess LangGraph after genuine branching/state requirements appear; no drag-and-drop builder now.
