# Data model

Load this reference when persistence, schema, lifecycle, relationships or migrations may change. SQLAlchemy models and Alembic migrations are the executable schema; this document describes ownership and invariants. Unless a section says otherwise, names below describe current implementation.

## Shared rules

- Tenant-owned data carries `workspace_id` directly or inherits it through a tenant-safe parent.
- IDs identify records; they never authorize access. Public resources use opaque public IDs while dense internal records use database identities.
- Cross-domain references must prove same-workspace ownership in a transaction or with tenant-safe composite constraints.
- PostgreSQL owns authoritative business state. Qdrant is a rebuildable retrieval projection.
- Use UTC timestamps, explicit lifecycle states, exact decimal money, and workspace-local time only for reporting boundaries.
- Store provider IDs as opaque, provider-namespaced values. Store tokens and credentials only as hashes or protected secret references.
- Prefer explicit archive/status/lifecycle semantics for entities referenced by operational history. Deleting a Product, Variant, Customer, Supplier or similar future record must not corrupt Orders, audit evidence or historical attribution.

## Current schema

### Aggregate ownership and lifecycle

| Aggregate | Workspace ownership and key relationships | Authoritative lifecycle/invariants |
|---|---|---|
| Workspace | Direct tenant root; members join authenticated users | Status-bound tenant; membership authorizes but IDs never do |
| Agent | Belongs to one workspace; revisions and Knowledge/Catalog assignments must match it | Editable draft plus immutable published revisions; pause/archive stops new use without deleting history |
| Knowledge document | Belongs to a workspace/base; versions produce generations/chunks | Only a selected ready generation is searchable; revocation precedes derived cleanup |
| Catalog product/variant | Belongs to one workspace; options, locations, collections and images remain tenant-safe | Lifecycle preserves identity rules; exact price and unknown stock semantics remain stable |
| Channel connection | Belongs to one workspace and binds one usable Agent revision | Active/revoked plus verified provider health; credential secrets live outside the record |
| Conversation | Belongs to workspace, Agent revision and channel; may link a Contact | Explicit lifecycle, workflow and AI/human handling state; messages/deliveries are idempotent |
| Contact | Belongs to one workspace; identities/leads/conversations link under explicit rules | Purpose-based retention; merges are logical, evidenced and reversible |
| Usage/analytics fact | Belongs to one workspace and optionally scoped operational entities | Append/idempotent factual evidence; no raw content or invented business result |

Cross-domain relationships never transfer ownership: an Agent assignment references Knowledge, a Conversation references an Agent revision, and a Contact links to a Conversation, but each owner retains its own invariants.

### Identity and workspaces

`users`, authentication sessions and email tokens own identity. `workspaces` and `workspace_members` own tenant membership and roles. A workspace is a generic tenant boundary; it has no required Commerce record.

### Agents

`agents` owns the generic assistant identity and lifecycle. `agent_revisions` stores immutable published snapshots. Current revisions and scopes include Commerce-era catalog configuration, assigned knowledge bases, locale, greeting, and instructions. That coupling is current implementation debt, not the definition of an Agent.

### Knowledge

Knowledge bases, documents, immutable document versions, generations, chunks, embedding profiles, embedding mappings, and ingestion jobs form the authoritative PostgreSQL graph. Document versions also own optional review time, next-review time and reviewer attribution; the API derives freshness rather than persisting a quality claim. The active-generation pointer selects the searchable version, so a candidate replacement or rebuild cannot displace the last ready generation before atomic cutover. `knowledge_recovery_events` records bounded owner/admin retry or rebuild attribution, reason and idempotency without copying source content. Qdrant points are indexed copies identified from this graph and may be recreated.

### Catalog and current inventory view

Products, variants, option definitions/values, collections, external references, images, size guides, locations, and location/variant assignments form the current Commerce catalog. Import tables preserve analyze, resolve, diff, and atomic commit evidence.

`inventory_levels` stores a current quantity for a workspace/location/variant. `NULL` means unknown and zero means known out of stock. It is not a movement ledger and cannot yet explain how a quantity changed.

### Channels and conversations

Channel connections, agent bindings, OAuth attempts, Website configuration, webhook events, thread/message mappings, outbound deliveries and receipts, response jobs, and quarantined inbound-media metadata implement Website, Facebook, and Zalo transport concerns.

Conversations own an agent/revision/channel association, handling mode, assignee, status, retention, messages, per-member read state, notes, tags, and scoped audit events. Website sessions bind opaque token hashes to trusted workspace, agent, revision, origin, and conversation state.

Evidence returned by the runtime is currently embedded in `conversation_messages.response_json`. Aggregate usage facts, including tool-call counts, live in `usage_events`. There are no current `message_evidence`, `agent_tool_calls`, or general `audit_logs` tables.

### Contacts and leads

Contacts own a workspace-level human profile, channel identities, notes, tags, assignment, retention, contact audit events, and reversible merge events. Leads preserve an originating consented conversion and link to a contact and conversation.

A Contact is channel/customer-service identity. It is not automatically a Commerce Customer: purchasing identity, addresses, tax data, and commercial history would have different rules and are not implemented.

### Analytics and usage

`usage_events` and monthly usage records support model/provider consumption and quotas without retaining prompts. `analytics_events` currently records a narrow allowlist of product-card facts. Conversation and contact audit tables are bounded, domain-specific trails rather than a platform-wide audit subsystem.

## Approved model direction

These concepts are approved boundaries, not existing tables:

- A domain-neutral agent configuration with optional capability assignments; existing revision shapes remain compatible until deliberately migrated.
- A durable, redacted execution record before the first tool can mutate business state. It should record the actor, authorized capability/action, idempotency key, status, safe request/result references, and timing without copying secrets or sensitive content.
- Commerce aggregates for Customer, Order, Order Line, Payment reference/status, Return, Supplier, Purchase Order, and Stock Movement only when their workflows are scheduled.
- An append-only stock movement ledger with a derived current balance before reservations, receipts, adjustments, sales, returns, or other operational stock mutations are introduced.

New domain tables must own their invariants and expose actions through their domain service. Agent configuration may reference a capability but must not duplicate the domain's authoritative state.

## Not implemented

- A generic plugin/capability registry or workflow engine.
- General-purpose tool-call and platform audit tables.
- Orders, checkout, payments, refunds, returns, suppliers, purchasing, POS, or a stock movement ledger.
- A Commerce Customer aggregate or automatic promotion of Contacts into customers.
- Qdrant as an authoritative store.

## Change triggers

- Before the first effectful agent action: define the minimum action contract, authorization policy, idempotency behavior, approval boundary, and durable execution evidence.
- Before the first operational inventory mutation: add the ledger, balance derivation, transaction rules, concurrency strategy, and migration/backfill plan.
- Before regulated payment or identity data: select an external provider, minimize retained data, and document webhook, reconciliation, failure, and deletion behavior.
