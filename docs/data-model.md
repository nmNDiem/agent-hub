# Data model reference

This is the canonical logical model. Alembic migrations and SQLAlchemy models are the executable schema; this document records ownership and invariants rather than duplicating every column.

## Common rules

- Tenant-owned rows carry `workspace_id` or a provably workspace-scoped composite parent relationship.
- Use UTC timestamps and explicit lifecycle state. Use workspace timezone only for reporting/calendar boundaries.
- Use UUIDv7 for `users.id`, `workspaces.id` and externally addressed IDs such as `agents.public_id`, `conversations.public_id` and visitor image handles. Generate UUIDv7 server-side through the tested adapter; never silently substitute UUIDv4 or require PostgreSQL native `uuidv7()`.
- Use BIGINT identity for dense internal rows such as memberships, products, variants, messages, documents, chunks, jobs and events. Provider/channel IDs remain opaque strings namespaced by provider and connection. Bearer/session tokens are cryptographically random values stored only as hashes, never UUIDv7.
- UUIDs identify resources but do not authorize access. Use `created_at` plus a deterministic tie-breaker for chronology rather than deriving business time from UUIDv7.
- Cross-domain references must prevent cross-workspace linkage with composite keys or equivalent transactional checks.
- Index by `workspace_id` plus the actual ordering/filter pattern. Avoid queries inside loops.
- Archive/revoke before destructive external cleanup when external state can fail.

## Identity and workspace

- `users`: UUIDv7 ID, normalized unique email, password hash, verification/status and timestamps.
- `auth_sessions`: user, refresh-token hash, expiry, revocation and rotation-family linkage.
- `email_tokens`: user, purpose, token hash, expiry and use time.
- `workspaces`: UUIDv7 ID, unique slug, display name, timezone, status and bounded settings.
- `workspace_members`: workspace, user and role; unique per pair.
- Later invitations and permission grants remain workspace-owned and cannot grant across tenants.

## Agents

- `agents`: BIGINT ID, UUIDv7 public ID, workspace, name, greeting, safe instructions, locale, lifecycle and catalog-scope mode.
- `agent_locations` / `agent_catalog_collections`: tenant-safe selected scope joins; `all` and empty selection remain distinct.
- `agent_knowledge_bases`: tenant-safe many-to-many assignments.
- `agent_revisions`: immutable versioned published configuration and policy references.
- Tool/policy configuration stores references and allowlists, never provider secrets in public config.

## Catalog

- `products`: workspace, optional reserved SKU, title/description/category/brand, exact nullable price, currency, approved URL, attributes and lifecycle.
- `product_variants`: tenant-safe product link, optional reserved SKU, name, nullable price override, inventory policy, option signature, attributes and lifecycle.
- `product_option_definitions`, `product_option_values`, `variant_option_values`: canonical ordered generic option dimensions; one variant selects at most one value per definition.
- `locations`, `location_variants`, `inventory_levels`: location metadata, nullable price/compare-price override and inventory keyed by workspace/location/variant. Quantity `NULL` is unknown; zero is known out of stock.
- `catalog_collections`, `catalog_collection_products`: reusable product subsets without copying products.
- `catalog_external_refs`: trusted `(workspace, source, namespace, external_id)` mapping to canonical entities.
- `product_images`: product/optional variant, managed private object or recorded remote reference, source/lifecycle and display metadata.
- `size_guides`: optional structured product/workspace guidance with source provenance.
- `catalog_imports`, staged records, issues and mapping profiles: persistent Analyze/Resolve/Diff evidence; Commit applies one atomic idempotent MERGE.

Product and variant SKU uniqueness is workspace-scoped and archived rows continue reserving identifiers. Price uses `NUMERIC(18,2)` and application `Decimal` with explicit currency.

## Knowledge and storage

- `knowledge_bases`: workspace, name/status, active and optional target embedding profile.
- `media_assets`: immutable private object metadata, byte count, checksum and cleanup state; original name is display-only.
- `knowledge_documents`: logical source identity and lifecycle.
- `knowledge_document_versions`: immutable manual/file versions.
- `knowledge_generations`: document version, immutable embedding profile, chunker/pipeline versions and `building | ready | failed | revoked` state.
- `knowledge_document_active_generations`: selects at most one ready generation per document.
- `knowledge_chunks`: workspace/generation, deterministic position, authoritative text, hash, locator and bounded metadata.
- `embedding_profiles`: provider, model, dimensions, provider revision, pipeline, distance metric, collection/config hash and immutable lifecycle.
- `knowledge_chunk_embeddings`: chunk/profile to deterministic Qdrant point, hash and index status.
- `ingestion_jobs` / `ingestion_job_attempts`: source/generation identity, state, attempt, lease, fencing, heartbeat and safe error code. At most one active job per document.

## Channels

- `channel_connections`: workspace, provider (`web | facebook | zalo`), display/external account identity, opaque credential reference, `active | revoked` lifecycle, health and timestamps. No credential value is stored in this table.
- `channel_agent_bindings`: one connection to its allowed agent and active published revision with tenant-safe keys.
- `website_channel_configs`: Website-only presentation and handoff configuration; origins remain in `widget_domains` and reference the shared connection.
- `channel_webhook_events`: connection/external event ID, payload fingerprint, received/processed state and safe error; unique per connection for dedupe. Raw payloads are not retained.
- `channel_thread_mappings`: a connection-namespaced external thread mapped to one normalized conversation.
- `channel_message_mappings`: a normalized message mapped to its connection/thread and optional provider message ID; IDs are unique only within the connection.
- `outbound_deliveries`: message, connection, idempotency key, attempt schedule, lease/fencing state, safe provider result and terminal/retryable state.

Raw provider payloads and access tokens are not general-purpose conversation metadata. Retain only fields needed for validation, retry, audit and supported rendering.

## Conversations

- `conversations`: BIGINT ID, UUIDv7 public ID, workspace, agent/revision, channel connection, optional Website session, `active | deleted` lifecycle, `open | pending | resolved` workflow status, `ai | human | paused` handling mode, last-message time and retention. Contact and assignee relationships arrive with their owning M1 tasks.
- `conversation_messages`: workspace/conversation, actor (`visitor | assistant | human | tool | system`), normalized text/evidence, `inbound | outbound` direction, processing state and timestamps. Provider delivery state is owned by `outbound_deliveries` rather than duplicated here.
- `message_evidence`: validated product/source references associated with a message.
- `agent_tool_calls`: redacted tool identity, result reference, status, latency and usage facts.
- `conversation_assignments`, `conversation_notes`, `conversation_tags`: workspace-safe operating workflow records.
- Website `widget_sessions` bind an opaque token hash to workspace, agent, revision, origin, conversation and expiry.

Provider retries map to the same normalized message/delivery record. AI/human handling mode is explicit; it is not inferred from the latest message text.

The Website migration preserves existing public conversation IDs, session links, request keys,
transcripts, leads, images, usage and retention deadlines. Social adapters must supply an
explicit retention deadline; they do not inherit the local Website 24-hour default.

## Contacts and leads

- `contacts`: workspace-owned profile with consent-aware display data, lifecycle and retention classification.
- `contact_identities`: contact plus namespaced identity type/provider/value hash or external ID, verification/consent evidence and uniqueness policy.
- `leads`: immutable originating workspace/conversation/session/agent/contact scope, optional validated email/phone/name, consent version/time, idempotency evidence, status and retention.
- `contact_notes`, `contact_tags`, `contact_assignments`: permissioned operational metadata.
- `contact_merge_events`: auditable reversible identity-link decisions; never merge by display name alone.

The current Website lead tables are the implemented starting point. M1 migrations must evolve them without creating a competing customer table or losing consent provenance.

## Usage and analytics

- `workspace_usage_months`: workspace-local month and transactional generated-turn reservations.
- `usage_events`: workspace/agent/conversation/channel, generation or vision kind, provider/model, observed calls/tokens/tools and status; no prompt/chat/image content.
- `analytics_events`: allowlisted product/channel/workflow events with minimal tenant-scoped dimensions and no unnecessary PII.
- `audit_logs`: actor, action, resource type/ID, redacted metadata and time.

Analytics aggregates derive from these facts or bounded source queries; they do not persist invented cost or duplicate raw content.

## Retention relationships

The local sweeper revokes expired Website sessions/conversations, removes transcript/lead PII, expires image grants/rate windows, retries private-image deletion and purges dependency-free tombstones. Usage facts remain content-free and may outlive a nullable conversation link. M1 must define retention for social provider IDs, messages, media and contacts before implementing their migrations.
