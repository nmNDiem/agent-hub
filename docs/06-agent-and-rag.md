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
- The API only validates/stages uploads and persists jobs. A separate worker process claims PostgreSQL jobs with `FOR UPDATE SKIP LOCKED`, bounded workspace concurrency, expiring leases, fencing tokens and heartbeats; the API process is not the durability mechanism.
- PDF extraction runs with strict `pypdf==6.19.0` parsing in an isolated child process with wall-clock, CPU, memory and output limits. Encrypted and scan/image-only PDFs are explicitly unsupported; OCR is not silently attempted.
- Chunk generations record the versioned chunker and parameters. Persist chunks before external calls, use deterministic vector point IDs, then atomically activate only a fully indexed generation. Deletion/archive revokes authoritative Postgres state before asynchronous Storage/vector cleanup.
- Retry only transient Storage/provider/network failures with capped exponential backoff and full jitter. Invalid content, unsupported PDF classes, hash mismatch, dimension mismatch and quota failures are permanent until the source or configuration changes.
- Persist immutable embedding profiles containing provider, model, dimensions, provider revision, pipeline version and distance metric. Never infer dimension from a model string or compare vectors from different profiles.
- The platform operator/provider bootstrap owns profile creation; workspaces never submit arbitrary model identifiers. A model change creates a new immutable profile and target collection, re-embeds every active source as a new generation, verifies coverage/isolation, and atomically changes the active profile. No profile is seeded when the exact model/dimensions are unapproved; documents remain `awaiting_profile` rather than using a guessed model.
- Treat Qdrant as a rebuildable derived index. Apply workspace and allowed-source filters **inside** vector retrieval, then revalidate returned chunks against the active ready generation in Postgres; test absence of other-tenant hits.

Uploaded and retrieved text remains untrusted data. Ingestion normalization does not make prompt injection safe; the actual instruction/data boundary, tool authorization and adversarial prompt tests belong to the grounded runtime before any content reaches a model.

## Answer rules
- Current effective catalog price (location override, otherwise variant override, otherwise product price) and location-scoped structured inventory override descriptive docs. `NULL` stock is unknown, not in-stock, while zero is known out of stock. F3 resolves allowed agent locations/collections before calling the F2.2 scoped search contract.
- Tool and card outputs use generic option/attribute labels. F3/F4 must not assume every catalog has `color`, `size`, variants or a size guide.
- Catalog replies include bounded channel-neutral conversational framing, while product facts remain in server-validated structured cards. Web may render cards visually; future social adapters may render the same facts as text or native product templates.
- Only claim a discount, size equivalence, returns policy or delivery promise when source data verifies it.
- Show a cited product card when possible; for unstructured answers cite source and avoid fabricated references.
- User/shop-uploaded instructions cannot override tenant security, tool policies or provider budget.
- If OpenAI is unavailable, show a transparent friendly error and optional human contact instead of inventing a response.

## Orchestration decision
Custom deterministic bounded orchestration + typed tools is CONFIRMED for the MVP grounded runtime. Reassess LangGraph only after genuine branching/state requirements appear; no drag-and-drop builder now. The model supplies bounded channel-neutral conversational framing and selects evidence references. The server validates those references and prohibited claims, requires knowledge paragraphs to be extractive from retrieved chunks, and constructs catalog product cards from current typed-tool results.
