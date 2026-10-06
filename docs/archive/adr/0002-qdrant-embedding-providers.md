# ADR-0002 — Qdrant knowledge index and embedding-provider boundary

Status: Accepted (2026-09-27).

## Context

F3 needs tenant-safe semantic retrieval without binding the knowledge domain or relational schema to one embedding vendor. The earlier pgvector direction was proposed, not confirmed. Model migrations may change provider, model identifier, dimensions and preprocessing/chunking behavior.

## Options considered

1. Store provider-specific vectors in Postgres/pgvector. This keeps one datastore but couples migrations and schema to a vector dimension and was not selected.
2. Use Qdrant as the authoritative knowledge store. This weakens relational lifecycle, authorization and recovery guarantees and was rejected.
3. Keep documents/chunks/jobs/profile state authoritative in Postgres and use Qdrant as a rebuildable derived vector index behind an interface. This is selected.

## Decision

- Qdrant is the confirmed semantic vector index. Postgres structured catalog search remains unchanged.
- PostgreSQL owns documents, chunk text, source locators, generations, ingestion jobs, active embedding profiles and index state. Qdrant never becomes the source of truth.
- The knowledge domain depends on `EmbeddingProvider` and `KnowledgeVectorIndex` interfaces. F3 implements OpenAI embeddings and Qdrant only. A Gemini or other provider requires a separate approved task and verified model identifier/dimensions.
- An immutable `embedding_profile` records `provider`, `model`, `dimensions`, optional provider model revision, AgentHub pipeline version, distance metric, Qdrant collection and configuration hash. Do not infer dimensions from a model name.
- Each embedding profile uses one shared Qdrant collection across workspaces. Do not create a collection per tenant. Every point carries `workspace_id`, knowledge/document/chunk identifiers, document generation, embedding profile and content hash. `workspace_id` is indexed as a tenant payload field.
- Every search injects validated workspace and allowed-source filters server-side. Returned point identifiers are loaded and revalidated against active, ready Postgres rows before prompt construction.
- Indexing is post-transactional and idempotent: persist authoritative rows/job first, embed, upsert Qdrant with a stable point ID, then mark indexed/ready. Qdrant success followed by a DB failure is safe to retry.
- Deletion or replacement revokes the Postgres generation first. Qdrant cleanup is asynchronous; stale points cannot become retrievable because active Postgres state is revalidated.
- Provider/model/pipeline migration creates a new embedding profile and collection, backfills it, validates coverage/isolation, atomically switches the active profile in Postgres, retains the previous profile for rollback, then removes it after an approved retention window.

## Consequences

- Qdrant is an additional runtime dependency with server-only credentials, health, persistence, backup/rebuild and cost considerations.
- Vector availability may fail independently of Postgres. Catalog-only answers can continue when policy allows; knowledge retrieval must fail transparently rather than use stale/unscoped data.
- Unit tests use fake embedding/vector adapters. F3 integration requires a real explicitly configured non-production Qdrant server and cross-workspace isolation tests.
- Exact OpenAI embedding model and dimensions remain configuration decisions. OpenAI stays the confirmed initial provider; the abstraction does not authorize a multi-provider marketplace or unused provider implementations.

## Reversibility

Postgres retains enough chunk content and immutable profile metadata to rebuild another vector store. Replacing Qdrant requires a new ADR, adapter, backfill and cutover; it does not require changing public business APIs or the canonical document model.

## Affected areas

F3 migrations and configuration, knowledge ingestion/retrieval, provider adapters, Qdrant payload/index setup, tenant isolation tests, deletion/retention, health/operations and deployment documentation.
