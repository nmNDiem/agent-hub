# AgentHub documentation router

This directory is the complete product and engineering knowledge base. It uses progressive disclosure: start from the active phase and primary domain, then load a canonical reference only when a real trigger applies.

> **Do not read all documentation by default.** Routine implementation should not preload product, architecture, roadmap, decisions, security, API, UI and unrelated domains “for completeness.”

Application code, migrations and generated OpenAPI remain executable authority for claims about current behavior. Documentation owns product intent, boundaries, invariants and approved scope.

## Start here

1. Read [`../AGENTS.md`](../AGENTS.md).
2. Find the explicitly approved implementation packet in [`phases/`](phases/).
3. Read only its **Required Context**.
4. Inspect its **Relevant Code Paths**.
5. Load **Conditional Context** only when the named trigger applies or discovery proves a dependency.

The roadmap selects and sequences phases; it does not authorize implementation. If no phase packet is explicitly approved, stop before coding.

## Route by function

| Change | Primary packet |
|---|---|
| Authentication, membership or tenant authorization | [`domains/identity-workspaces.md`](domains/identity-workspaces.md) |
| Agent configuration, publishing or runtime behavior | [`domains/agents.md`](domains/agents.md) |
| Knowledge ingestion, indexing or retrieval | [`domains/knowledge.md`](domains/knowledge.md) |
| Catalog, products, variants or imports | [`domains/catalog.md`](domains/catalog.md) |
| Inventory availability or future stock operations | [`domains/inventory.md`](domains/inventory.md) |
| Channel-neutral messaging integration | [`domains/channels.md`](domains/channels.md) |
| Inbox, messages or AI/human handling | [`domains/conversations.md`](domains/conversations.md) |
| Contacts, identities, leads or merges | [`domains/contacts.md`](domains/contacts.md) |
| Usage or operational metrics | [`domains/analytics.md`](domains/analytics.md) |
| Commerce boundary or transactional expansion | [`domains/commerce.md`](domains/commerce.md) |
| AgentHub subscriptions or entitlements | [`domains/platform-billing.md`](domains/platform-billing.md) |

Domain packets are the primary routine working context. They distinguish **CURRENT**, **APPROVED DIRECTION**, **NOT IMPLEMENTED** and concrete change triggers.

## Load canonical references only when triggered

| Trigger | Conditional authority |
|---|---|
| Product definition or scenario changes | [`product.md`](product.md) |
| Module ownership, dependency direction or runtime boundary changes | [`architecture.md`](architecture.md) |
| Persistence, schema, lifecycle or migration changes | [`data-model.md`](data-model.md) plus executable models/migrations |
| Durable design question not settled by the phase/domain packet | [`decisions.md`](decisions.md) |
| Authentication, authorization, sensitive data or side effects | Relevant section of [`security.md`](security.md) |
| External HTTP/SSE/DTO/error/idempotency contract changes | Relevant section of [`api.md`](api.md) |
| Normal frontend behavior or accessibility changes | [`ui.md`](ui.md) plus the primary domain |
| World UI work | Route through [`ui/world/README.md`](ui/world/README.md); never preload the whole package |
| Test strategy or permanent scenario coverage changes | Relevant section of [`testing.md`](testing.md) |
| Deployment, provider setup, retention jobs or recovery | Relevant section of [`operations.md`](operations.md) |
| Payments; regulated financial billing flows; e-invoicing; digital signatures; accounting-service functionality; marketplace/e-commerce-platform behavior; sensitive AI use cases; or material personal-data processing changes | Relevant section of [`compliance.md`](compliance.md) |
| Selecting or sequencing a phase | [`roadmap.md`](roadmap.md) |
| Facebook or Zalo protocol detail | Route through [`refs/channels/README.md`](refs/channels/README.md) after the provider trigger applies |

## Authority map

| Concept | One authoritative home |
|---|---|
| Product definition and scenarios | [`product.md`](product.md) |
| Architecture and dependency boundaries | [`architecture.md`](architecture.md) |
| Logical data ownership/model | [`data-model.md`](data-model.md) |
| Durable decisions | [`decisions.md`](decisions.md) |
| Domain behavior | [`domains/`](domains/) |
| Approved implementation contract | [`phases/`](phases/) |
| Roadmap and phase sequencing | [`roadmap.md`](roadmap.md) |
| API conventions | [`api.md`](api.md) |
| Security invariants | [`security.md`](security.md) |
| Compliance and regulated-capability boundaries | [`compliance.md`](compliance.md) |
| Product-wide UX | [`ui.md`](ui.md) |
| Provider deep references | [`refs/channels/README.md`](refs/channels/README.md) |

Historical task detail belongs in Git history. Do not create a parallel `tasks/` layer or duplicate authoritative rules inside a phase packet.

`compliance.md` is conditional authority, not default reading. Do not load it for ordinary Agent, Knowledge, UI, Catalog, or other work that does not meet its trigger.

## Status vocabulary

- **CURRENT** — present in executable code/migrations.
- **APPROVED DIRECTION** — durable future constraint.
- **PLANNED** — selected roadmap work, not implemented.
- **FUTURE / UNSCHEDULED** — allowed direction, not a commitment.
- **NON-GOAL** — explicitly excluded from the stated scope.
- **TRIGGER** — event that requires loading more context or adding a boundary.
