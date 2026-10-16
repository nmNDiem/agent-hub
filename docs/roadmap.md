# Delivery roadmap

The roadmap preserves shipped history and selects coherent phases. `Complete` describes the repository today. `Approved next` is agreed direction but still requires an explicitly approved packet under [`phases/`](phases/). `Unscheduled` is intentionally not a commitment.

The roadmap is planning context, not a routine implementation contract. Every implementation phase needs a goal, user outcome, scope, non-goals, architecture/data/API/UI/security impacts, tests, acceptance criteria and context manifest before coding.

## F0–F5 foundation

Status: **Complete**

| Delivery | Shipped outcome |
|---|---|
| F0 Foundation | Repository, API/dashboard/widget skeleton, configuration, CI, migrations, and local boot |
| F1 Identity and tenancy | Authentication, sessions, workspaces, membership, and tenant boundaries |
| F2 Catalog | Products, variants, options, locations, collections, images, and spreadsheet import |
| F3 Knowledge and agents | Private ingestion, OpenAI/Qdrant adapters, grounded runtime, typed read tools, and Playground |
| F4 Website widget and vision | Publishing, scoped visitor sessions, streaming, product cards, and visitor images |
| F5 Local operations | Consented leads, conversation history, usage/quota, retention, and observability |

Detailed delivery history remains in Git rather than being restated as current product definition.

## M1 — Omnichannel operations

Status: **Complete**

Website, Facebook Messenger, and Zalo now share normalized connection, conversation, contact, delivery, retry, and human-handoff foundations. The unified inbox supports explicit AI/human mode, assignment, unread state, status, notes, tags, delivery state, consent-aware contacts, identity linking/merge history, and persisted operational analytics.

Commerce remains visible in product-card analytics and the current assistant runtime, but M1 did not make Commerce mandatory for every workspace.

## M2 — General-purpose agent quality and experience

Status: **Approved next**

Goal: prove that AgentHub can configure, ground, evaluate, publish, and operate an agent without requiring Commerce while improving quality for existing Commerce users.

| Phase | Outcome | Status |
|---|---|---|
| [M2.1 General-purpose Agent baseline](phases/M2.1-general-purpose-agent-baseline.md) | Domain-neutral Agent defaults/runtime behavior and permanent knowledge-only plus Commerce regression scenarios | Next candidate; packet awaits explicit implementation approval |
| M2.2 Agent evaluation and rollout evidence | Evaluation cases, feedback, unresolved-question review, regression comparison and safe rollout evidence | Planned; packet not written |
| M2.3 Knowledge quality and freshness | Source freshness, version visibility, ingestion recovery and retrieval diagnostics | Planned; packet not written |
| M2.4 Guided onboarding | Capability-aware setup and publish-readiness checks | Planned; packet not written |
| M2.5 Capability-aware product navigation | Contextual domain presentation proven by real non-Commerce and Commerce flows | Planned; packet not written |
| M2.6 World vertical prototype | Accessible spatial projection with approved dependencies and conventional-navigation parity | Planned; packet not written |

Non-goals: effectful business actions, a generic plugin registry, a workflow canvas, and broad UI replacement without behavior parity.

## M3 — SaaS commercialization

Status: **Approved direction; unscheduled**

- Workspace invitations and richer role administration.
- Plans, entitlements, commercial quotas, subscriptions, invoices, and signed billing webhooks.
- Operator controls with narrowly scoped support access and auditable account lifecycle actions.

Platform billing is separate from Commerce payments taken by a workspace from its customers.

## Capability-triggered foundations

Status: **Unscheduled**

These are introduced by the first real use case, not built speculatively:

- Before the first effectful tool: typed action contract, server-side authorization, validation, idempotency, approval policy, and durable redacted execution evidence.
- Before the first stock mutation: append-only stock movements and transactionally derived balances.
- Before payments/refunds or other regulated actions: external-provider-first integration, webhook verification, reconciliation, and minimal sensitive-data retention.

## Optional Commerce expansion

Status: **Unscheduled**

Commerce is the first substantial domain capability and remains optional. Its likely dependency order is inventory ledger, transactional order model, external payment references, fulfillment/returns, then suppliers and purchasing. POS is considered only after the same order and inventory invariants can support it without a parallel source of truth.

See [`domains/commerce.md`](domains/commerce.md) and [`domains/inventory.md`](domains/inventory.md).

## Explicitly not planned

- Autonomous unrestricted payments, refunds, order placement, or stock changes by an LLM.
- Arbitrary-code tools or arbitrary URL fetching.
- A speculative plugin marketplace, universal capability registry, or drag-and-drop workflow engine.
- Microservice extraction without measured ownership, scaling, or deployment pressure.
