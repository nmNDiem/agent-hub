# 04 — Initial data model (design, not executed migration)

Use **UUIDv7 only for `users.id`, `workspaces.id` and public IDs on externally addressed resources such as `agents.public_id` and `conversations.public_id`**. Use BIGINT IDENTITY for dense internal PKs (agents, products, variants, messages, chunks, sessions and logs). PostgreSQL stores UUIDv7 in type `uuid`; generate UUIDv7 in the backend rather than assuming a PostgreSQL 18 `uuidv7()` default. No blanket UUID PK rule. See `architecture/identifiers.md` and `architecture/data-model.md`. Use `created_at`/`updated_at` UTC timestamps. `workspace_id` on every tenant-owned record, including chunks, messages, tool calls and usage. For child FKs, consider composite `(workspace_id, parent_id)` references or equivalent transactional checks to prevent cross-tenant linkage. Index by workspace plus primary access pattern. Avoid deleting audit/financially significant data casually.

**Canonical vocabulary:** `workspace` is the tenant (a shop in the fashion UI); `agent` is the domain entity (a chatbot in the UI). Public identifiers are unprefixed, lowercase UUIDv7; internal BIGINT values never act as public visitor conversation/agent IDs. This file lists logical fields, while `architecture/sql/001_reference_schema.sql` is illustrative partial DDL, **not an executable full migration**.

## Identity / tenancy
- `users`: id, normalized_email (unique), password_hash, email_verified_at, status, timestamps.
- `auth_sessions`: id, user_id, refresh_token_hash, expires_at, revoked_at, rotated_from_id, user_agent_hash/ip metadata (minimized).
- `email_tokens`: user_id, purpose, token_hash, expires_at, used_at; never persist raw reset token.
- `workspaces`: id, slug (unique), display_name, status, settings_json.
- `workspace_members`: id, workspace_id, user_id, role enum OWNER/ADMIN/MEMBER; unique(workspace_id,user_id).

## Agents / channels
- `agents`: BIGINT id, UUIDv7 public_id, workspace_id, name, greeting, safe_instructions, default_locale, status DRAFT/PUBLISHED/PAUSED, model_config_ref (no keys), created_by.
- `agent_channels`: id, workspace_id, agent_id, type WEB (later FACEBOOK/ZALO), config, enabled.
- `widget_domains`: id, workspace_id, agent_id, normalized_origin; uniqueness per agent/origin.
- `widget_sessions`: id, workspace_id, agent_id, token_hash or signed session id, expires_at, privacy/consent state, visitor_key_hash.

## Catalog
- `products`: id, workspace_id, product_sku, title, description, category, status, product_url, currency, price, timestamps; product SKU is normalized uppercase and unique per workspace where supplied. Archived rows continue reserving their SKU.
- `product_variants`: id, workspace_id, product_id, variant_sku, name, price_override, stock_quantity nullable, inventory_policy, deterministic option_signature, legacy color/size compatibility fields, status and timestamps; variant SKU is normalized uppercase and unique per workspace where supplied. Archived rows continue reserving their SKU.
- `product_option_definitions`, `product_option_values`, `variant_option_values`: normalized, ordered generic variant dimensions and values. These tables are the option source of truth; `color` and `size` are compatibility projections only.
- `products.attributes_json`, `product_variants.attributes_json`: flexible non-identity facts that should not become variant dimensions. Identity, pricing, stock and options remain relational rather than being hidden in attribute JSON.
- `catalog_external_refs`: trusted source/namespace/external-ID mappings used for deterministic reconciliation; display names are never identity.
- `product_images`: id, workspace_id, product_id, variant_id nullable, storage_path or un-fetched remote reference, source kind, sort_order, alt_text and lifecycle state. Import analysis/commit never fetches arbitrary remote URLs.
- `catalog_imports`, normalized staged records, issues and mapping profiles: persisted universal-import evidence and decisions. Analyze never mutates the canonical catalog; commit revalidates and applies an atomic idempotent MERGE.
- `size_guides`: id, workspace_id, product_id nullable, structured_content, source_id nullable.
Catalog prices use `NUMERIC(18,2)` and application `Decimal`, never binary floats. `price_override = NULL` inherits the product price while `0` is an explicit zero price. Currency is an explicit ISO code such as VND. `stock_quantity = NULL` means unknown, while `0` means known out of stock; `inventory_policy` supplies the interpretation without collapsing those states. Products may exist without variants, options or a size guide, and the canonical model is not fashion-specific.

## Knowledge
- `knowledge_bases`: id, workspace_id, name, kind, status.
- `agent_knowledge_bases`: workspace_id, agent_id, knowledge_base_id (join).
- `knowledge_documents`: id, workspace_id, knowledge_base_id, filename, mime, storage_path, checksum, version, status, error_code, updated_at.
- `knowledge_chunks`: id, workspace_id, document_id, content, position, embedding (dimension decided by selected model), source_locator, metadata_json.
- `ingestion_jobs`: id, workspace_id, document_id, status, attempts, last_error_redacted, timestamps, idempotency_key.

## Conversations / usage
- `conversations`: BIGINT id, UUIDv7 public_id, workspace_id, agent_id, widget_session_id, status, last_message_at, retention_until.
- `messages`: id, workspace_id, conversation_id, actor VISITOR/ASSISTANT/TOOL, text, safe_attachment_refs, timestamps, metadata.
- `agent_tool_calls`: id, workspace_id, conversation_id, tool_name, argument_summary_redacted, result_ref, status, latency_ms.
- `leads`: id, workspace_id, conversation_id, name, email, phone, consent_at, consent_text_version, followup_status.
- `usage_events`: id, workspace_id, agent_id, conversation_id nullable, provider, model, token_counts, estimate_cost, event_time.
- `audit_logs`: id, workspace_id, actor_user_id nullable, action, resource_type, resource_id, metadata_redacted, occurred_at.

## Tenant isolation indexes / invariants
- `products(workspace_id,status,category)`; `product_variants(workspace_id,product_id)`; option joins by variant/definition/value; external refs by workspace/source/external ID; import jobs by workspace/status; `messages(workspace_id,conversation_id,created_at)`; `knowledge_chunks(workspace_id,document_id)` plus vector index suited to chosen dimensions/index strategy.
- No cross-workspace FK relationship; select/search/universal import/embedding jobs restricted to workspace.
- Soft-archive products and agents; retention/purge policy for visitor content must be documented before production.
- Use DB uniqueness and transactional updates for imports, refresh rotation and idempotent lead submissions.
