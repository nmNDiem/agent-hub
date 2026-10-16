# Commerce capability

## Function and boundary

Commerce is AgentHub's first substantial optional domain capability. It supplies structured product and, later, transactional operations to authorized Agents and workspace users. Core Workspace, Agent, Knowledge, Channel, Conversation, and Contact behavior must work without it.

## CURRENT

- Catalog products, variants, options, collections, locations, images, prices, size guidance, import, and read-only agent tools.
- Current inventory quantities by location/variant, without a movement ledger.
- Product-card evidence and impression analytics.
- Contacts/leads that support service follow-up but are not Commerce Customers.

## Capability status map

| Area | Status | Meaning |
|---|---|---|
| Catalog | **IMPLEMENTED** | Products, variants, options, collections, locations, media, pricing, import, and read tools |
| Inventory | **PARTIAL FOUNDATION** | Current quantities only; no operational movement ledger |
| Customers / CRM | **PARTIAL FOUNDATION** | Generic Contacts/leads exist; Commerce Customer, purchase history, segmentation, and loyalty do not |
| Commercial analytics | **PARTIAL FOUNDATION** | Product impressions and operational conversation/lead measures; no revenue or attribution |
| Sales / Orders / Fulfillment / Returns | **FUTURE / UNSCHEDULED** | Requires transactional order and inventory foundations |
| Purchasing / Suppliers | **FUTURE / UNSCHEDULED** | No supplier, purchase-order, receipt, or payable state |
| Payments / Promotions / Tax / Shipping | **FUTURE / UNSCHEDULED** | External-provider-first where regulated; no current transactional implementation |
| POS | **FUTURE / UNSCHEDULED** | May follow only by reusing shared order, payment, customer, and inventory truth |

## Core flow

Maintain/import catalog → assign catalog scope to an Agent → retrieve validated product facts during a conversation → render evidence through supported channels → record an impression fact.

## Ownership map

| Concern | Owner |
|---|---|
| Product presentation and variant identity | Catalog |
| Stock facts and future movements | Inventory |
| Communication identity and consent | Contacts |
| Future purchasing identity | Commerce Customer |
| Future order lifecycle | Orders |
| Future payment execution/data | External payment provider; AgentHub stores minimal references/status |
| Agent access | Server-authorized capability/action invoking the owning domain service |

## Invariants

- Enabling Commerce is explicit and contextual; it never changes Workspace or Agent semantics.
- Structured Commerce facts do not come from RAG or model output.
- Read tools return bounded, server-authorized facts with validated evidence.
- Effectful actions must pass through the owning domain service, never write tables from the model/runtime layer.
- Contact-to-Customer linkage is explicit and auditable, not inferred.
- Payments and other regulated services are external-provider-first with minimal retained sensitive data.

## APPROVED DIRECTION

The likely dependency order is: inventory ledger → transactional orders → external payment references/status → fulfillment/returns → suppliers/purchasing. POS is considered only when it can reuse the same order, customer, payment, and inventory truths.

Each aggregate is added for a concrete workflow. There is no requirement to implement the whole sequence as one program.

When Orders are introduced, Order owns transaction state; lines snapshot relevant SKU/description/options/unit price/currency/tax/discount facts so history does not depend on mutable Catalog values. Inventory changes go through Inventory, payment state comes from verified provider/domain records, and channel-triggered creates require idempotency.

Payment integration uses an external licensed provider. AgentHub may create payment requests, present provider options, verify webhooks, keep minimal operational references/status, and reconcile Orders. Wallets, stored value, custody, lending, credit, and unlicensed intermediation require separate product, legal, security, and architecture approval.

## NOT IMPLEMENTED

Commerce Customer, cart/checkout, orders/order lines, reservations, payments/refunds, fulfillment, returns, suppliers, purchase orders, POS, discounts/promotions, tax, shipping, or a stock movement ledger.

## Change triggers

- First operational stock mutation: satisfy [`inventory.md`](inventory.md) before coding the workflow.
- First transactional purchase: define Order lifecycle, pricing snapshot, idempotency, concurrency, cancellation, and Contact/Customer policy.
- First money movement: select an external provider and define webhook verification, reconciliation, failures, disputes, and refunds.
- First effectful Agent action: satisfy the action boundary in [`agents.md`](agents.md).

Related authority: [`catalog.md`](catalog.md), [`inventory.md`](inventory.md), [`contacts.md`](contacts.md), [`../architecture.md`](../architecture.md).
