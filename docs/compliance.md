# Compliance and regulated-capability boundaries

This is a conditional product and architecture reference. Load it only when a phase touches payments, billing involving regulated financial flows, electronic invoicing, digital signatures, accounting-service functionality, marketplace/e-commerce-platform behavior, sensitive AI use cases, or material personal-data processing changes. It is not routine context for ordinary Agent, Knowledge, UI, Catalog, or non-regulated operational work.

This document records design constraints and review triggers. It does not determine jurisdiction-specific obligations or replace qualified legal advice. An approved phase must identify applicable markets, providers, data flows, and required legal/product review before implementation.

## Capability boundary

| Boundary | Capabilities | Product and architecture consequence |
|---|---|---|
| **Own normally** | Catalog, Inventory, Orders, POS, CRM, Suppliers, Purchasing, operational analytics, and accounting/reporting software functionality | AgentHub may own application workflows and authoritative operational records, subject to normal security, privacy, tax, retention, and local-law review. Owning software functionality does not authorize providing a regulated professional or financial service. |
| **Integration-first** | Payment processing, electronic invoicing, digital signatures/trust services, regulated accounting services, and banking/credit-related services | Prefer qualified external providers. AgentHub may orchestrate requests, retain the minimum operational references and statuses, verify provider events, and reconcile domain records. Provider selection does not remove AgentHub's security, privacy, audit, or user-disclosure obligations. |
| **Separate approval required** | Custody of customer or merchant funds, stored-value wallets, unlicensed payment intermediation, lending/credit, regulated accounting-service provision, and operation as a trust-service or certificate-authority provider | Do not implement directly without explicit owner-approved legal, product, security, and architecture decisions. A roadmap mention or adjacent integration is not approval. |

## Cross-cutting compliance triggers

### AI regulation

Sensitive or consequential AI use cases require a scoped review of role, risk classification, disclosures, human oversight, evaluation, record keeping, explainability, prohibited practices, and provider obligations in each target jurisdiction. Model output remains untrusted and cannot directly mutate authoritative state. Ordinary low-risk Agent improvements do not require loading this document unless their use or data changes materially.

### Personal-data processing

Material changes to personal-data categories, purpose, lawful basis, consent, profiling/segmentation, automated decisions, retention, deletion, cross-border transfer, subprocessors, or data-subject workflows require privacy and security review. Collect and retain only what the approved workflow needs; do not infer sensitive attributes for Commerce segmentation or loyalty.

### E-commerce website or application operation

Customer-facing websites or applications that advertise, contract, sell, or facilitate Commerce may trigger registration, notification, merchant-information, consumer-protection, tax, record-retention, or disclosure duties. The phase must identify the operator model and target jurisdictions before launch.

### Marketplace or platform scenarios

Multi-merchant listing, matching, contracting, fee collection, seller administration, or platform-mediated fulfillment is not a routine extension of a single workspace's Commerce tools. It requires a separate compliance review covering platform/operator classification, merchant onboarding, content/product obligations, consumer complaints, tax, data sharing, payment flow, and marketplace registration or notification.

### Financial and payment functionality

Payment initiation, processing, refunds, settlement, stored value, custody, remittance, lending, credit, or banking connectivity must document who controls funds, who is merchant of record, the licensed provider's role, webhook authenticity, idempotency, reconciliation, disputes, refunds, failure recovery, sensitive-data scope, and audit retention. AgentHub defaults to recording and orchestrating provider-backed activity, not holding funds.

### Accounting and reporting

AgentHub may provide bookkeeping, accounting, tax-calculation, reporting, export, and operational record software. Representing the business, certifying filings, or providing a regulated accounting service is a distinct service boundary and needs separate approval or an appropriately qualified provider.

### Electronic invoicing and digital signatures

Electronic-invoice workflows should integrate with qualified providers where registration, numbering, transmission, signing, archival, or tax-authority connectivity is regulated. Integrating an electronic-signature or trust-service provider is distinct from AgentHub operating as a trust service or certificate authority. Direct provision requires separate approval.

## Phase requirements when triggered

An affected phase packet must state:

- target jurisdictions and the concrete compliance trigger;
- AgentHub's role and each external provider's role;
- authoritative records, minimum retained sensitive data, retention, deletion, audit, and access boundaries;
- authorization, consent/disclosure, idempotency, verification, reconciliation, failure, dispute, and support behavior as applicable;
- any registration, notification, contract, policy, or separate legal/product approval required before release.

Compliance review constrains an approved feature; it does not authorize speculative provider abstractions, payment systems, marketplaces, accounting services, trust services, or capability frameworks.
