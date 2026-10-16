# Decision register

This register contains durable product and architecture decisions. Current behavior belongs in domain/technical documents; sequencing belongs in [`roadmap.md`](roadmap.md).

## Confirmed decisions

| Area | Decision | Rationale | Consequence | Revisit trigger |
|---|---|---|---|---|
| Product | AgentHub is a general-purpose AI Agent platform; fashion Commerce is the first substantial domain capability. | Portfolio, Commerce and internal-assistant scenarios share the same platform concerns. | Core documentation and new core code must not assume a catalog. | Owner changes the product definition. |
| Workspace | Workspace is a generic tenancy/isolation boundary, not a shop or permanent business type. | Capability needs change over time and workspaces may be non-commercial. | No required Commerce records or permanent type discriminator. Historical shop wording may remain where harmless. | A concrete requirement needs mutually exclusive tenant behavior that capabilities cannot express simply. |
| Agent | Use one generic Agent aggregate; behavior derives from configuration, Knowledge, authorized Tools, policies, Channels and immutable revisions. | Avoids duplicated platform lifecycle and runtime logic. | Do not add `sales_agents`, `portfolio_agents` or similar foundational models by default. | A concrete domain proves a genuinely different aggregate lifecycle/invariant. |
| Domain ownership | Each domain owns its authoritative data and mutations. | Agents and Channels must not become alternate systems of record. | Agent configuration/Qdrant never duplicate current catalog, inventory, order or payment truth. | Never; only ownership may be deliberately reassigned by an approved migration. |
| Agent actions | Long-term execution is `Agent -> authorized typed Tool/Action -> Domain Service -> domain state`. | Keeps model output untrusted and business rules enforceable. | Workspace scope is server-injected; services reauthorize; high-impact actions may require approval. | The first effectful tool triggers the minimal authorization/audit implementation. |
| Tool infrastructure | Do not build a speculative plugin framework, universal registry, service locator or workflow engine. | No current second implementation justifies the complexity. | Add only the smallest composition boundary required by an approved tool use case. | A concrete second/third tool family demonstrates repeated integration needs. |
| Knowledge | PostgreSQL owns Knowledge sources, versions, chunks and active generations; Qdrant is derived/rebuildable. | Deletion, tenancy and lifecycle require relational authority. | Vector hits are filtered and revalidated; structured mutable facts stay outside RAG. | A replacement must preserve equivalent authority and rebuild semantics. |
| Runtime provider | OpenAI remains behind server-side generation, vision and embedding adapters. | This is the approved implemented stack. | No extra model provider without an approved task-specific reason. | Reliability, capability, legal or commercial evidence justifies another provider. |
| Architecture | Use a domain-oriented modular monolith and `router/adapter -> service -> repository/provider`. | Current scale benefits from local transactions and lower operational complexity. | No microservice split, Redis or distributed workflow framework by default. | Measured scaling, isolation or deployment requirements exceed the monolith. |
| Commerce | Commerce is an optional first-class domain capability and current functionality is preserved. | It is valuable implemented product depth without defining all workspaces. | Extend it additively; do not rename/rehome working modules for visual purity. | A functional blocker requires a bounded migration. |
| Inventory | Current quantity is sufficient for read availability; operational mutation requires a transactional service and auditable stock movements. | POS, returns and transfers need proof of why stock changed. | No POS/order fulfillment/return mutation may write levels as an unaudited number. | First approved operational stock mutation. |
| Contact/customer | Contact is a generic cross-channel identity/relationship; it is not automatically a Commerce Customer. | Non-commerce conversations also produce contacts. | Future Commerce customer profile may link to Contact through an explicit domain decision. | Commerce customer lifecycle is approved. |
| Payments/regulation | Prefer licensed external providers for payments and other regulated services. | Avoids casual custody/intermediary/regulatory scope. | AgentHub may orchestrate requests, verify events and reconcile records; no wallets/custody/lending by default. | Separate owner-approved product, legal, security and architecture review. |
| Compatibility | Preserve working APIs, identifiers, routes and schema unless a concrete requirement authorizes change. | Migration cost and risk outweigh cosmetic consistency. | Historical `/create-shop` or commerce-oriented names may remain as naming debt. | The name causes a proven functional/security/user blocker. |
| UI | UI represents user tasks and meaningful relationships, not the database schema. | A table-per-navigation CMS obscures agent operation. | Use progressive disclosure and contextual domain UI; avoid filler and duplicate facts. | User research or a concrete workflow proves a different information architecture. |

## Confirmed technology and data choices

- Next.js/strict TypeScript dashboard and independent TypeScript/Vite widget.
- FastAPI/Python 3.12 backend with SQLAlchemy async and Alembic.
- Supabase PostgreSQL and private Storage; Supabase Vault for channel credentials.
- FastAPI-owned email/password authentication, not Supabase Auth.
- UUIDv7 and BIGINT usage as specified in [`data-model.md`](data-model.md).
- Typed bounded custom orchestration rather than an agent framework.
- Durable PostgreSQL jobs with leases/fencing for ingestion and outbound work.
- Current Catalog truth uses exact Decimal prices, generic options, locations and nullable inventory where `NULL` differs from zero.

## Open operating choices

These do not reopen product architecture:

- exact production model IDs, embedding dimensions and budgets;
- production retention periods and jurisdiction-specific privacy wording;
- Zalo/provider prerequisites and supported provider-specific message classes;
- production domains, backup objectives and external connector vendors;
- commercial plan structure and payment provider for platform billing.

Owner instructions may supersede a decision. Update this register, affected authority documents and the approved task together; do not silently reinterpret an open implementation choice as permission to change the product or stack.
