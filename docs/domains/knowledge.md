# Knowledge

## Function and ownership

Knowledge provides grounded workspace-specific context. PostgreSQL owns sources, versions, chunks, and activation state; Qdrant is a derived search index. Knowledge complements rather than replaces structured domain facts.

## CURRENT

- Multiple knowledge bases assignable to agents.
- Manual text and private PDF/TXT versions.
- Durable ingestion jobs with leases, fencing, heartbeat, and classified retries.
- Isolated PDF parsing, deterministic chunks, immutable embedding profiles, OpenAI embeddings, and tenant-filtered Qdrant retrieval.
- Atomic active-generation cutover, rebuild, and stale-point revalidation.
- Knowledge-only Agents can publish and execute without Commerce records; their runtime omits Catalog instructions, tools and product rendering.

Main data: knowledge bases/documents/versions/generations/chunks, embedding profiles/mappings, media assets, ingestion jobs/attempts. Main surfaces: Knowledge management and agent assignment.

## Core flow

Create source/version → enqueue generation → parse and chunk into PostgreSQL → embed/index in Qdrant → mark generation ready → atomically select it as active → retrieve with server-injected tenant/source filters → revalidate returned chunks in PostgreSQL.

## Invariants

- Only a complete ready generation is searchable.
- Retrieved text and documents are untrusted input, never instructions.
- Revocation happens in PostgreSQL before asynchronous vector/storage cleanup.
- Catalog price, SKU, options, and stock never come from RAG.
- Failed indexing remains observable and retryable; errors are not silently swallowed.

## APPROVED DIRECTION

Controlled URL sources, source freshness, version comparison, retrieval diagnostics, safe additional formats, and quality signals for missing/conflicting knowledge.

## NOT IMPLEMENTED

No unrestricted web crawler, arbitrary URL fetch tool, continuously self-editing knowledge, or Qdrant-authored state exists.

## Change trigger

Each new source type needs explicit trust, parsing, size, synchronization, retention, and failure policy before ingestion support.

## Dependencies and conditional references

- Agent assignment behavior belongs to [`agents.md`](agents.md).
- Load [`../data-model.md#knowledge`](../data-model.md#knowledge) for persistence changes, [`../security.md#uploads-and-retention`](../security.md#uploads-and-retention) for new inputs/retention, and [`../operations.md`](../operations.md) for provider or worker operations.

## Relevant code paths

- `apps/api/src/agent_hub_api/knowledge/`
- `apps/web/src/features/knowledge/`
- `apps/api/src/agent_hub_api/agents/` only when retrieval/runtime composition changes
