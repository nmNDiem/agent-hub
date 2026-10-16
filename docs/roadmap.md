# Delivery roadmap

The roadmap preserves shipped history and selects coherent phases. `Complete` describes accepted delivery present in the repository. `Next candidate` identifies sequencing, but implementation still requires an explicitly approved packet under [`phases/`](phases/). `Unscheduled` is intentionally not a delivery commitment.

The roadmap is planning context, not a routine implementation contract. Every implementation phase needs a goal, user outcome, scope, non-goals, architecture/data/API/UI/security impacts, tests, acceptance criteria and context manifest before coding.

Numbered sections provide one stable reading order. Decimal identifiers name delivery phases within a section; dependency gates, rather than numbering alone, determine when planned phases may safely interleave.

## 1 — Foundation

Status: **Complete**

| Delivery | Shipped outcome |
|---|---|
| 1.1 Repository foundation | Repository, API/dashboard/widget skeleton, configuration, CI, migrations, and local boot |
| 1.2 Identity and tenancy | Authentication, sessions, workspaces, membership, and tenant boundaries |
| 1.3 Catalog | Products, variants, options, locations, collections, images, and spreadsheet import |
| 1.4 Knowledge and Agents | Private ingestion, OpenAI/Qdrant adapters, grounded runtime, typed read tools, and Playground |
| 1.5 Website widget and vision | Publishing, scoped visitor sessions, streaming, product cards, and visitor images |
| 1.6 Local operations | Consented leads, conversation history, usage/quota, retention, and observability |

Detailed delivery history remains in Git rather than being restated as current product definition.

## 2 — Omnichannel operations

Status: **Complete**

Website, Facebook Messenger, and Zalo now share normalized connection, conversation, contact, delivery, retry, and human-handoff foundations. The unified inbox supports explicit AI/human mode, assignment, unread state, status, notes, tags, delivery state, consent-aware contacts, identity linking/merge history, and persisted operational analytics.

Commerce remains visible in product-card analytics and the current assistant runtime, but this delivery did not make Commerce mandatory for every workspace.

## 3 — General-purpose Agent quality and experience

Status: **In progress; 3.2 is the next candidate**

Goal: prove that AgentHub can configure, ground, evaluate, publish, and operate an agent without requiring Commerce while improving quality for existing Commerce users.

| Phase | Outcome | Status |
|---|---|---|
| [3.1 General-purpose Agent baseline](phases/3.1-general-purpose-agent-baseline.md) | Domain-neutral Agent defaults/runtime behavior and permanent knowledge-only plus Commerce regression scenarios | Complete |
| [3.2 Agent evaluation and rollout evidence](phases/3.2-agent-evaluation-and-rollout-evidence.md) | Evaluation cases, feedback, unresolved-question review, regression comparison and safe rollout evidence | Next candidate; packet awaits explicit implementation approval |
| [3.3 Knowledge quality and freshness](phases/3.3-knowledge-quality-and-freshness.md) | Source freshness, version visibility, ingestion recovery and retrieval diagnostics | Planned; proposed packet awaits explicit approval |
| 3.4 Guided onboarding | Capability-aware setup and publish-readiness checks | Planned; packet not written |
| 3.5 Capability-aware product navigation | Contextual domain presentation proven by real non-Commerce and Commerce flows | Planned; packet not written |
| 3.6 World vertical prototype | Accessible spatial projection with approved dependencies and conventional-navigation parity | Planned; packet not written |

Non-goals: effectful business actions, a generic plugin registry, a workflow canvas, and broad UI replacement without behavior parity.

## Future cross-domain capability directions

Status: **Planned direction; unscheduled and without implementation packets**

General-purpose growth does not stop at knowledge-only Agents or Commerce. Future work may equip Agents with authorized domain tools in other optional workspace capabilities:

| Capability direction | Intended boundary |
|---|---|
| Booking | Availability, resources, appointments, reservations, cancellations, reminders, and provider/calendar synchronization under an owning domain service |
| Forms | Typed form definitions, validation, submissions, consent, review, and bounded follow-up actions |
| Email and Calendar | Provider-backed mail and calendar reads/actions with server-side authorization, scoped credentials, idempotency, audit, and approval where required |
| Documents | Authorized document templates, generation, review, storage, retrieval, and lifecycle operations without treating model output as authoritative by default |
| Custom/internal API tools | Explicitly configured, typed, allowlisted integrations to approved business APIs; never arbitrary URL fetching or client-asserted authority |
| Controlled automations/workflows | Concrete triggers and bounded actions with authorization, idempotency, audit, failure recovery, human approval, and ownership defined before execution |

These directions are optional per workspace and require concrete user workflows before implementation phases are selected. They do not authorize a speculative universal plugin registry, arbitrary-code tools, or a generic workflow engine. Shared action infrastructure is introduced only when an approved capability proves the need.

## Capability-triggered foundations

Status: **Unscheduled**

These are introduced by the first real use case, not built speculatively:

- Before the first effectful tool: typed action contract, server-side authorization, validation, idempotency, approval policy, and durable redacted execution evidence.
- Before the first stock mutation: append-only stock movements and transactionally derived balances.
- Before payments/refunds or other regulated actions: external-provider-first integration, webhook verification, reconciliation, and minimal sensitive-data retention.
- Before electronic invoicing, digital signatures, marketplace/platform behavior, regulated accounting services, or material sensitive-data/AI changes: load the conditional constraints in [`compliance.md`](compliance.md) and obtain any required legal/product approval.

## 4 — Commerce operations

Status: **Major planned product track; phase packets not yet written**

Commerce is optional for each workspace but is not an optional product priority. AgentHub is planned to grow this track toward retail and business operations comparable in scope to products such as KiotViet, while the Platform/Core, portfolio, and internal-assistant experiences continue to work without Commerce. Commerce is not a prerequisite for non-Commerce Agents.

The remaining section 3 phases remain the next platform-quality priority. Commerce phases may follow or interleave with later platform work only when their stated foundations are ready and an explicit phase packet is approved. Nothing in this roadmap authorizes implementation by itself.

| Phase | Planned outcome | Dependency gate |
|---|---|---|
| 4.1 Inventory integrity and operations | Append-only stock movement ledger, transactionally maintained balances, transfers, stocktakes, authorized adjustments, reason/source evidence, and auditable inventory history | Required before any order, purchasing, return, or POS flow mutates stock |
| 4.2 Orders, customers, pricing, and fulfillment | Orders and immutable price snapshots, order items, pricing/promotion rules, lifecycle and fulfillment state, idempotent creation, returns foundation, Commerce Customer linked explicitly to generic Contact, purchase history, segmentation, and a loyalty foundation only when justified | Requires 4.1 transactional inventory semantics; effectful Agent actions additionally require authorization, audit, idempotency, failure, and approval foundations |
| 4.3 Suppliers and purchasing | Supplier records, purchase orders, receipts, and operational supplier balances/records that post inventory changes through the shared ledger | Requires 4.1; receipt and balance semantics must be specified in the approved packet |
| 4.4 POS and retail operations | Location-aware checkout, barcode workflows, cart, application of pricing/promotions and discounts, cashier/session concepts where required, and returns/exchanges | Requires 4.1 and 4.2; POS must use shared Orders, Customers, and Inventory rather than create parallel truth |
| 4.5 Payments and invoicing integrations | Payment requests, provider integrations, minimal payment records, verified webhooks, reconciliation, refund orchestration, and electronic-invoice integration | Requires provider selection plus reconciliation design; regulated capabilities remain integration-first and follow [`compliance.md`](compliance.md) |
| 4.6 Commerce analytics and AI operations | Revenue, margin, inventory health, sell-through, purchasing analytics, operational alerts, and authorized Agent/AI insights over authoritative Commerce data | Requires the owning transactional domains; analytics and model output never become transaction truth |

The sequencing is dependency-driven rather than a promise that every phase ships contiguously. Phase 4.3 may proceed after 4.1 independently of later sales UI, while 4.5 may be introduced alongside the first approved payment-requiring Order or POS workflow. Phase 4.6 grows only from implemented authoritative data. Each phase should remain coherent rather than split into dozens of infrastructure-only packets.

See [`domains/commerce.md`](domains/commerce.md) and [`domains/inventory.md`](domains/inventory.md).

## 5 — SaaS commercialization

Status: **Approved direction; unscheduled**

| Phase | Planned outcome |
|---|---|
| 5.1 Workspace administration | Workspace invitations and richer role administration |
| 5.2 Plans and platform billing | Plans, entitlements, commercial quotas, subscriptions, invoices, and signed billing webhooks |
| 5.3 Operator controls | Narrowly scoped support access and auditable account lifecycle actions |

Platform billing is separate from Commerce payments taken by a workspace from its customers.

## Explicitly not planned

- Autonomous unrestricted payments, refunds, order placement, or stock changes by an LLM.
- Arbitrary-code tools or arbitrary URL fetching.
- A speculative plugin marketplace, universal capability registry, or drag-and-drop workflow engine.
- Microservice extraction without measured ownership, scaling, or deployment pressure.
