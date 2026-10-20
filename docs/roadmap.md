# Delivery roadmap

This roadmap preserves shipped history and sequences coherent product outcomes. `Complete` means accepted behavior is present in the repository. `Next candidate` selects the next planning target but does not authorize implementation. `Planned` and `Unscheduled` are not delivery commitments.

The roadmap is planning context, not a routine implementation contract. Every implementation phase requires an explicitly approved packet under [`phases/`](phases/) with a user outcome, scope, non-goals, architecture/data/API/UI/security impacts, tests, acceptance criteria and context manifest.

Numbering provides one stable reading order. Dependency gates, rather than numbering alone, determine when phases may safely interleave. New roadmap entries describe work an Agent or operator can complete; implementation primitives such as Forms, Documents, Calendar APIs or tool schemas do not become product phases by themselves.

## 1 — Foundation

Status: **Complete**

| Delivery | Shipped outcome |
|---|---|
| 1.1 Repository foundation | Repository, API/dashboard/widget skeleton, configuration, CI, migrations and local boot |
| 1.2 Identity and tenancy | Authentication, sessions, workspaces, membership and tenant boundaries |
| 1.3 Catalog | Products, variants, generic options, locations, collections, images and source-agnostic spreadsheet import |
| 1.4 Knowledge and Agents | Private ingestion, OpenAI/Qdrant adapters, grounded runtime, typed read tools and Playground |
| 1.5 Website widget and vision | Publishing, scoped visitor sessions, streaming, product cards and visitor images |
| 1.6 Local operations | Consented leads, conversation history, usage/quota, retention and observability |

Detailed delivery history remains in Git rather than being restated as current product definition.

## 2 — Omnichannel operations

Status: **Complete**

Website, Facebook Messenger and Zalo share normalized connection, conversation, contact, delivery, retry and human-handoff foundations. The unified inbox supports explicit AI/human mode, assignment, unread state, status, notes, tags, delivery state, consent-aware contacts, identity linking/merge history and persisted operational analytics.

These capabilities remain Platform/Core. Future workflows reuse the same Conversations, Contacts and handover state rather than creating channel-specific or workflow-specific substitutes.

## 3 — General-purpose Agent core

Status: **In progress; 3.2 is approved for implementation**

Goal: make the Agent the primary product interaction and establish trustworthy Knowledge plus a safe path to real work without requiring Commerce.

| Phase | User-visible outcome | Status and dependency |
|---|---|---|
| [3.1 General-purpose Agent baseline](phases/3.1-general-purpose-agent-baseline.md) | Domain-neutral defaults/runtime behavior and permanent Knowledge-only plus Commerce regression scenarios | **Complete** |
| [3.2 Agent workspace experience](phases/3.2-agent-workspace-experience.md) | An Agent-centric workspace for creating, configuring, grounding, testing, publishing, observing and operating Agents through a contextual World and accessible focused screens | **Approved for implementation** |
| [3.3 Knowledge quality and freshness](phases/3.3-knowledge-quality-and-freshness.md) | Source freshness, immutable version visibility, ingestion recovery and retrieval diagnostics | **Complete** |
| [3.4 Agent actions and real-work execution](phases/3.4-agent-actions-and-follow-up-requests.md) | The typed `contacts.follow_up.request` workflow records explicit Website/Facebook/Zalo follow-up requests through a server-bound, idempotent Contacts transaction with redacted execution evidence | **Complete — 2026-10-20; privacy review remains a production release gate** |

Phase 3.2 includes minimum guidance, honest empty/error/readiness state and capability-aware navigation. It does not absorb full guided onboarding. Phase 3.4 must grow from a real user workflow; it is not permission to build a universal action platform, capability registry or workflow engine.

## 4 — General-purpose real-world workflows

Status: **4.1 complete**

These phases prove that AgentHub is useful outside Commerce. They are named after work completed for a user, not the internal primitives used to implement it. Each phase reuses the action safety boundary introduced by the first approved effectful workflow and adds only infrastructure demonstrated by that workflow.

| Phase | User-visible outcome | Dependency gate |
|---|---|---|
| [4.1 Qualified contact and structured intake](phases/4.1-qualified-contact-and-structured-intake.md) | An Agent can naturally collect, validate and persist an operator-defined contact/service intake, while a human owns qualification | **Complete — 2026-10-20; privacy/security review remains a production release gate** |
| 4.2 Information and document delivery | An Agent can select and send an authorized document or information package with attributable delivery state | Requires a concrete delivery channel/provider, content authorization and failure/audit policy |
| 4.3 Email, calendar and appointment workflows | An Agent can arrange, confirm, reschedule and cancel an appointment against authoritative availability and approved provider state | Requires typed actions, resource/timezone rules, idempotency, confirmation and reconciliation |
| 4.4 External and internal system actions | An Agent can invoke explicitly configured, typed and allowlisted business operations without arbitrary URL or arbitrary-code execution | Requires concrete target APIs, credential ownership, authorization and safe failure semantics |
| 4.5 Controlled automations | Operators can enable bounded triggers over stable real actions with visible status, pause/disable, retry, audit and loop protection | Requires implemented actions and real events; no automation engine is built in anticipation |

Forms, Documents, Email, Calendar, webhooks and API clients may appear inside these workflows as tools or workflow components. They are not automatically peer business domains or top-level navigation. Existing human handover from section 2 remains available across all workflows.

## 5 — Commerce operations

Status: **Major planned product track; Catalog baseline is complete; operational phase packets are not written**

Commerce is optional for a workspace but remains AgentHub's first substantial business domain and a major product priority. It is expected to grow toward operational breadth comparable to retail-management products while remaining native to both human and Agent actors over one authoritative state.

The completed Catalog baseline already provides products, variants, generic options, images, collections, locations, pricing, current nullable inventory and source-agnostic spreadsheet import. The phases below extend that baseline; they must not re-plan shipped Catalog work as absent.

| Phase | Planned outcome | Dependency gate |
|---|---|---|
| 5.1 Inventory integrity and operations | Append-only stock movements, transactionally maintained balances, transfers, stocktakes, authorized adjustments, receiving and auditable history | Required before Orders, Purchasing, Returns or POS mutate stock |
| 5.2 Orders, customers, pricing and fulfillment | Orders and line snapshots, Commerce Customer linked explicitly to Contact, pricing/promotions, lifecycle, cancellation, fulfillment and returns foundation | Requires 5.1 for stock effects; Agent mutations also require the effectful-action boundary |
| 5.3 Suppliers and purchasing | Supplier records, purchase orders, receipts, costs, supplier history and applicable operational balances/returns | Requires 5.1; receipt/variance and payable ownership must be explicit |
| 5.4 POS and retail operations | Location-aware checkout, barcode/cart, customer selection, approved pricing/discounts, payment method, returns/exchanges and relevant staff/session concepts | Requires 5.1 and 5.2; POS reuses Orders, Customers, Pricing and Inventory truth |
| 5.5 Payment and electronic-invoice integrations | Provider-backed payment requests/status/reconciliation/refunds and electronic-invoice workflow integrations | Requires provider selection, compliance review and the first approved payment-requiring workflow |
| 5.6 Commerce analytics and AI operations | Revenue, margin, inventory health, sell-through, purchasing analytics, operational alerts and authorized Agent insights | Requires the owning transactional domains; derived output never becomes transaction truth |

Branches/locations, receivables/payables, loyalty, staff/shift operations and deeper reports enter the relevant phase only when a concrete workflow requires them. Commerce work may interleave with section 4 when it proves shared Agent-action architecture, but it must not redefine Platform/Core or block all cross-domain progress.

See [`domains/commerce.md`](domains/commerce.md), [`domains/catalog.md`](domains/catalog.md) and [`domains/inventory.md`](domains/inventory.md).

## 6 — Agent quality and rollout

Status: **Planned; baseline quality remains mandatory in every earlier phase**

| Phase | Planned outcome | Dependency gate |
|---|---|---|
| [6.1 Agent evaluation and rollout evidence](phases/6.1-agent-evaluation-and-rollout-evidence.md) | Centralized evaluation suites, regression comparison, feedback review, observability and evidence for a human rollout decision | Benefits from stable Agent workflows and action-specific regression cases; not approved for implementation |

This section systematizes quality; it does not defer correctness. Every earlier capability must ship its own business-critical tests, tenant-isolation coverage, side-effect tests and regression cases.

## 7 — SaaS commercialization

Status: **Approved direction; unscheduled**

| Phase | Planned outcome |
|---|---|
| 7.1 Workspace administration | Invitations and richer role administration |
| 7.2 Plans and platform billing | Plans, entitlements, commercial quotas, subscriptions, invoices and signed billing webhooks |
| 7.3 Operator controls | Narrowly scoped support access and auditable account-lifecycle actions |

Commercialization follows demonstrated Agent value, real workflows and domain operation. Platform billing remains separate from payments a workspace receives from its customers.

## 8 — Guided onboarding

Status: **Planned after the interaction model and real workflows stabilize**

| Phase | Planned outcome | Dependency gate |
|---|---|---|
| 8.1 Guided onboarding and publish readiness | End-to-end setup guidance, capability discovery, workflow-aware readiness and role-appropriate launch assistance | Requires stable 3.2 interaction, real capabilities/actions and meaningful publish-readiness rules |

Useful empty states, next-step suggestions, inline explanations, validation and actionable errors are required from phase 3.2 onward; they are not postponed to section 8.

## Cross-phase foundations introduced only when triggered

- Before each new effectful action: typed input/output, server-side authorization, validation, Agent permission, confirmation/approval policy, idempotency, execution status, predictable errors, durable redacted audit evidence and reconciliation where external state exists.
- Before the first stock mutation: append-only stock movements and transactionally derived/reconciled balances.
- Before payment, refund, electronic invoicing, digital signing, marketplace/platform behavior, regulated financial/accounting behavior or material sensitive-data/AI changes: load [`compliance.md`](compliance.md), identify AgentHub/provider roles and obtain any required legal/product/security approval.
- Before automation: at least one stable real action and a real trigger, with scope, authorization, audit, retry, disable/pause, visibility and loop prevention.

## Explicitly not planned

- A Commerce-only product, generic CMS, developer console for AI primitives or disconnected collection of Forms/Documents/Calendar/Booking modules.
- Autonomous unrestricted payments, refunds, Orders, appointment changes or stock mutations by an LLM.
- Arbitrary-code tools, arbitrary URL fetching or client-asserted authority.
- A speculative plugin marketplace, universal capability registry, generic action platform or drag-and-drop workflow engine.
- Empty provider implementations, one Agent model per use case or one microservice per domain.
- A 3D game, decorative AI imagery, fake operational activity or spatial UI without an accessible conventional path.
- Treating the quality phase as permission to omit tests now, or the onboarding phase as permission to omit guidance now.
