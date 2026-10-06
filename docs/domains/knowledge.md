# Knowledge

## Purpose

Knowledge supplies grounded workspace-specific context such as shop profile, FAQ, policies and size guidance. It does not replace structured catalog facts.

## Current capability

- Multiple workspace knowledge bases assignable to agents.
- Manual text and private PDF/TXT document versions.
- Durable PostgreSQL ingestion jobs with leases, fencing, heartbeat and classified retries.
- Isolated PDF parsing, deterministic chunks and immutable embedding profiles.
- OpenAI embeddings and tenant-filtered Qdrant indexing/retrieval.
- Active-generation cutover, rebuild and stale-point revalidation.

## Complete domain capability

- Website/URL sources and controlled scheduled synchronization.
- More safe document formats where justified.
- Source freshness, lifecycle policy and stale-content review.
- Version comparison, retrieval diagnostics and content-quality workflow.
- Agent-quality signals that identify missing or conflicting knowledge.

## Invariants

- PostgreSQL owns source text, versions, chunks and active generation state; Qdrant is derived.
- Only a complete ready generation becomes searchable.
- Every vector query contains server-injected workspace/allowed-source filters and results are revalidated in PostgreSQL.
- Documents and retrieved text are untrusted input, never executable instructions.
- Deletion revokes authoritative access before asynchronous vector/Storage cleanup.
- Catalog price, SKU, options and stock are never sourced from RAG.

Storage and processing details are in [`../reference/storage.md`](../reference/storage.md).
