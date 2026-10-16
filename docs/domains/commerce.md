# Commerce capability

## Function and boundary

Commerce is AgentHub's first substantial optional domain capability and a major planned product track. It supplies structured product and, over planned phases, retail and business operations to authorized workspace users and Agents. Enabling Commerce is a workspace choice: Core Workspace, Agent, Knowledge, Channel, Conversation, and Contact behavior must continue to work without it.

Optional capability does not mean optional product priority. The planned Commerce track grows toward operational breadth comparable to retail/business systems such as KiotViet without turning Commerce into a prerequisite for non-Commerce Agents.

## CURRENT

- Catalog products, variants, options, collections, locations, images, prices, size guidance, import, and read-only Agent tools.
- Current inventory quantities by location/variant, without a movement ledger or transactional operational mutations.
- Product-card evidence and impression analytics.
- Generic Contacts/leads that support service follow-up but are not Commerce Customers.

Current core flow: maintain/import Catalog → assign Catalog scope to an Agent → retrieve validated product facts during a conversation → render evidence through supported Channels → record an impression fact.

## Capability map

| Capability | Status | Authoritative boundary |
|---|---|---|
| Catalog | **CURRENT** | Catalog owns product/variant identity, options, collections, media, locations, pricing, import, and bounded read tools |
| Inventory availability | **CURRENT — LIMITED** | Inventory levels hold current quantity only; there is no stock ledger or auditable operational history |
| Product/conversation analytics | **CURRENT — LIMITED** | Product impressions and existing operational conversation/lead measures exist; revenue, margin, sell-through, and purchasing analytics do not |
| Generic Contact/lead | **CURRENT** | Contacts owns cross-channel identity, consent, lead state, linking, and merge history; a Contact is not automatically a Commerce Customer |
| Inventory operations | **PLANNED — 5.1** | Inventory will own stock movements, transactionally derived balances, transfers, stocktakes, adjustments, and auditable history |
| Orders and sales | **PLANNED — 5.2** | Orders will own order lifecycle, order items, immutable price snapshots, fulfillment state, idempotency, and returns foundation |
| Pricing and promotions | **PLANNED — 5.2 / 5.4** | Commerce will own explicit price-list, discount, and promotion rules; Orders snapshot applied results and POS consumes the same rules |
| Commerce Customer / CRM | **PLANNED — 5.2** | Commerce will own purchase-oriented profile/history, segmentation, and any justified loyalty state, with an explicit auditable link to generic Contact |
| Suppliers and purchasing | **PLANNED — 5.3** | Purchasing will own suppliers, purchase orders, receipts, and operational supplier balances/records; receipts will post through Inventory |
| POS and retail operations | **PLANNED — 5.4** | POS will provide checkout, barcode, cart, discount/promotion application, cashier/session, return/exchange, and location-aware workflows over shared Orders and Inventory |
| Payments and invoicing integrations | **PLANNED — 5.5** | AgentHub will orchestrate provider-backed requests, records, verified webhooks, reconciliation, refunds, and electronic-invoice integration without default fund custody |
| Commerce analytics and AI operations | **PLANNED — 5.6** | Analytics will derive revenue, margin, inventory health, sell-through, purchasing measures, alerts, and authorized insights from owning-domain records |

No **PLANNED** row describes implemented entities, APIs, screens, services, or schema.

## Planned dependency order

1. **5.1 — Inventory integrity and operations:** establish an append-only stock ledger and transactional inventory before any operational stock mutation, including transfers, stocktakes, adjustments, receipts, reservations, sale deductions, returns, and corrections as approved.
2. **5.2 — Orders, customers, pricing, and fulfillment:** build idempotent Orders, price/promotion rules and snapshots, Commerce Customer purchase history/segmentation/loyalty foundations, fulfillment, and returns foundations on transactional Inventory.
3. **5.3 — Suppliers and purchasing:** add supplier records, purchase orders, operational balances/records, and receipt workflows whose inventory changes and corrections use the same ledger.
4. **5.4 — POS and retail operations:** add checkout, barcode, cart, cashier/session, location-aware sales, promotion/discount application, and return/exchange workflows by reusing Orders, Customers, Pricing, and Inventory truth.
5. **5.5 — Payments and invoicing integrations:** introduce provider-backed payment requests/records, webhook verification, reconciliation, refund orchestration, and electronic-invoice integration when an approved sales workflow needs them.
6. **5.6 — Commerce analytics and AI operations:** derive revenue, margin, inventory health, sell-through, purchasing analytics, alerts, and Agent/AI insights only after the relevant authoritative transactional data exists.

This order expresses dependency gates, not a requirement that every phase ship contiguously. Phase 5.3 can proceed after 5.1 independently of 5.4. Phase 5.5 can accompany the first approved payment-requiring Order or POS workflow once provider and reconciliation boundaries are defined. Every phase requires its own approved implementation packet.

Effectful Agent actions are independently gated on typed action contracts, server-side authorization, input validation, idempotency, audit/attribution, failure behavior, and approval policy where required. Model output never directly mutates Commerce state.

## Source-of-truth boundaries

| Concern | Authoritative owner |
|---|---|
| Product and variant presentation identity | Catalog |
| Stock movement history and derived availability | Inventory |
| Cross-channel identity and communication consent | Contacts |
| Purchase-oriented customer state | Planned Commerce Customer, linked explicitly to Contact |
| Price lists, discounts, promotions, and eligibility rules | Planned Commerce pricing capability; Orders snapshot applied results and POS does not fork the rules |
| Order, line snapshot, fulfillment, and return lifecycle | Planned Orders domain |
| Supplier, purchase order, and receipt lifecycle | Planned Purchasing domain |
| Checkout and cashier interaction | Planned POS workflow over Orders, Customers, and Inventory; never parallel transaction truth |
| Provider payment execution and regulated invoice/signature execution | Qualified external provider |
| Operational payment/invoice references, verified status, and reconciliation | Planned AgentHub integration records owned by the applicable Commerce domain |
| Agent access | Server-authorized typed action invoking the owning domain service |
| Commerce measures and AI insights | Derived Analytics views over authoritative domain records; never a mutation source |

Order lines must snapshot relevant SKU, description, selected options, unit price, currency, tax, and discount facts so historical sales do not depend on mutable Catalog values. Inventory mutations must use immutable source references to Orders, Purchasing, Returns, or POS-originated Orders and remain transactionally auditable.

## Regulatory and provider boundaries

AgentHub normally owns Commerce application functionality such as Catalog, Inventory, Orders, POS, CRM, Suppliers, Purchasing, operational analytics, and accounting/reporting software. Regulated execution remains integration-first.

- Payment processing, electronic invoicing, digital signatures/trust services, regulated accounting services, and banking/credit-related services should use qualified external providers.
- AgentHub may initiate requests, verify signed events, retain minimum operational references/status, reconcile domain records, and orchestrate authorized refunds.
- AgentHub does not default to custody of customer or merchant funds and does not directly provide stored-value wallets, unlicensed payment intermediation, lending/credit, regulated accounting services, or trust-service/CA operation.
- Direct provision of those regulated capabilities requires explicit owner-approved legal, product, security, and architecture decisions.
- Marketplace or multi-merchant platform behavior is not implied by workspace Commerce and requires a separate compliance review.

Load [`../compliance.md`](../compliance.md) only when its payment, regulated billing, e-invoicing, digital-signature, accounting-service, marketplace/platform, sensitive-AI, or material personal-data trigger applies.

## Invariants

- Commerce enablement is explicit and contextual; it never changes generic Workspace or Agent semantics.
- Structured Commerce facts come from owning PostgreSQL domains, not RAG, prompts, Qdrant, or model output.
- Read tools return bounded, server-authorized facts with validated evidence.
- Effectful actions pass through owning domain services and their authorization, transaction, audit, and idempotency rules.
- Contact-to-Customer linkage is explicit and auditable, not inferred.
- POS uses shared Orders and Inventory; it does not create a separate sales or stock source of truth.
- Provider callbacks and client claims are untrusted until authenticated, verified, authorized, and reconciled.
- Analytics and Agent insights are derived from authoritative Commerce data and cannot silently rewrite it.

## NOT IMPLEMENTED

Stock movement ledger; transactional transfers, stocktakes, adjustments, reservations, receipts, sale deductions, or returns; Commerce Customer; cart/checkout; Orders/order items; price snapshots; fulfillment; returns; suppliers; purchase orders; payment/refund records and integrations; electronic invoicing; POS; discounts/promotions; tax/shipping operations; revenue/margin/inventory-health/sell-through/purchasing analytics; Commerce operational alerts; and effectful Commerce Agent actions.

Do not infer implementation authority for these capabilities from this domain map or the roadmap.

## Change triggers

- First operational stock mutation: satisfy [`inventory.md`](inventory.md), including ledger design and migration, before coding the workflow.
- First transactional purchase: define Order lifecycle, price/promotion authority and snapshots, inventory transactions, idempotency/concurrency, cancellation, fulfillment/returns, and Contact/Customer policy.
- First promotion or discount: define eligibility, precedence/stacking, time/location/customer scope, authorization, rounding/tax interaction, snapshot, and audit behavior.
- First supplier receipt: define Purchasing ownership, receipt/variance behavior, supplier records/balances, and Inventory source references.
- First POS workflow: prove reuse of Orders, Customers, Inventory, location, payment, return, and discount rules without parallel truth.
- First money movement or refund: select a qualified provider and define webhook verification, authorization, reconciliation, failure, dispute, sensitive-data, and refund behavior; load [`../compliance.md`](../compliance.md).
- First e-invoice, signature, accounting-service, marketplace/platform, sensitive-AI, or material personal-data change: load [`../compliance.md`](../compliance.md) and record required review/approval in the phase packet.
- First effectful Agent action: satisfy the action boundary in [`agents.md`](agents.md).

## Dependencies and conditional references

- Current product facts belong to [`catalog.md`](catalog.md); stock evolution belongs to [`inventory.md`](inventory.md); communication identity remains in [`contacts.md`](contacts.md).
- Load [`../architecture.md#platformcore-workflow-components-and-domain-systems`](../architecture.md#platformcore-workflow-components-and-domain-systems) only when changing the Platform/Commerce dependency boundary.
- Load [`../compliance.md`](../compliance.md) only for its stated triggers, not for routine Catalog or Commerce-read work.

## Relevant code paths

- `apps/api/src/agent_hub_api/catalog/` and `apps/web/src/features/catalog/` for the implemented capability
- No Order, Payment, Purchasing, POS, stock-ledger, or separate Commerce Customer module exists today
