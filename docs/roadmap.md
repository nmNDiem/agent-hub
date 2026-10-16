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
- Before electronic invoicing, digital signatures, marketplace/platform behavior, regulated accounting services, or material sensitive-data/AI changes: load the conditional constraints in [`compliance.md`](compliance.md) and obtain any required legal/product approval.

## Commerce operations track

Status: **Major planned product track; phase packets not yet written**

Commerce is optional for each workspace but is not an optional product priority. AgentHub is planned to grow this track toward retail and business operations comparable in scope to products such as KiotViet, while the Platform/Core, portfolio, and internal-assistant experiences continue to work without Commerce. Commerce is not a prerequisite for non-Commerce Agents.

M2 remains the next platform-quality track. Commerce phases may follow or interleave with later platform work only when their stated foundations are ready and an explicit phase packet is approved. Nothing in this roadmap authorizes implementation by itself.

| Phase | Planned outcome | Dependency gate |
|---|---|---|
| C1 Inventory integrity and operations | Append-only stock movement ledger, transactionally maintained balances, transfers, stocktakes, authorized adjustments, reason/source evidence, and auditable inventory history | Required before any order, purchasing, return, or POS flow mutates stock |
| C2 Orders, customers, and fulfillment | Orders and immutable price snapshots, order items, lifecycle and fulfillment state, idempotent creation, returns foundation, Commerce Customer linked explicitly to generic Contact, purchase history, segmentation, and a loyalty foundation only when justified | Requires C1 transactional inventory semantics; effectful Agent actions additionally require authorization, audit, idempotency, failure, and approval foundations |
| C3 Suppliers and purchasing | Supplier records, purchase orders, receipts, and operational supplier balances/records that post inventory changes through the shared ledger | Requires C1; receipt and balance semantics must be specified in the approved packet |
| C4 POS and retail operations | Location-aware checkout, barcode workflows, cart, discounts, cashier/session concepts where required, and returns/exchanges | Requires C1 and C2; POS must use shared Orders, Customers, and Inventory rather than create parallel truth |
| C5 Payments and invoicing integrations | Payment requests, provider integrations, minimal payment records, verified webhooks, reconciliation, refund orchestration, and electronic-invoice integration | Requires provider selection plus reconciliation design; regulated capabilities remain integration-first and follow [`compliance.md`](compliance.md) |
| C6 Commerce analytics and AI operations | Revenue, margin, inventory health, sell-through, purchasing analytics, operational alerts, and authorized Agent/AI insights over authoritative Commerce data | Requires the owning transactional domains; analytics and model output never become transaction truth |

The sequencing is dependency-driven rather than a promise that every phase ships contiguously. C3 may proceed after C1 independently of later sales UI, while C5 may be introduced alongside the first approved payment-requiring order or POS workflow. C6 grows only from implemented authoritative data. Each phase should remain coherent rather than split into dozens of infrastructure-only packets.

See [`domains/commerce.md`](domains/commerce.md) and [`domains/inventory.md`](domains/inventory.md).

## Explicitly not planned

- Autonomous unrestricted payments, refunds, order placement, or stock changes by an LLM.
- Arbitrary-code tools or arbitrary URL fetching.
- A speculative plugin marketplace, universal capability registry, or drag-and-drop workflow engine.
- Microservice extraction without measured ownership, scaling, or deployment pressure.
