# Product

Load this authority when defining product meaning, users, permanent scenarios, acceptance principles or non-goals. Routine implementation should rely on its approved phase and primary domain packet instead.

## Product thesis

AgentHub is where individuals and organizations create, configure, equip, deploy and operate AI Agents that have trusted knowledge, communicate through multiple channels and perform real work on authorized business or external systems.

An Agent behaves like an AI staff member. It must increasingly be able to:

1. understand its identity and whom it represents;
2. use assigned Knowledge;
3. communicate through appropriate Channels;
4. understand each Conversation's context;
5. perform permitted real work;
6. use only the domain systems and external services it is authorized to use;
7. hand work to a person when needed; and
8. make its current and historical operation understandable to an operator.

AgentHub is not a Commerce SaaS with a chatbot attached, a generic CMS, a developer console for AI tools, an abstraction-first framework or a disconnected set of Forms/Documents/Calendar/Booking modules. Fashion Commerce is the first substantial implemented domain capability and remains a major product direction, but Platform/Core must work without Commerce.

The priority order is:

```text
useful Agent
  -> clear Agent experience
  -> trustworthy Knowledge
  -> permitted real work
  -> sufficiently deep domains for real workflows
  -> quality, control and commercialization
```

Do not reverse this into framework, abstraction, admin screens and billing before proving that the Agent is useful.

## Core mental model

```text
Agent
├── Identity
├── Instructions
├── Knowledge
├── Conversations
├── Channels
├── Actions
├── State
└── Handover
```

The product should help an operator answer: Who is this Agent? What does it know? Where does it operate? With whom is it speaking? What may it do? What is it doing now? What has it done? When does it need a person?

Forms, Documents, webhooks, schemas, Calendar APIs and similar implementation primitives may exist underneath workflows. They are not the primary user mental model and do not automatically deserve a domain, module or top-level menu. Prefer “the Agent can schedule an appointment” to “Booking capability enabled.”

## Product hierarchy

```text
AgentHub
├── Agents
│   ├── Knowledge
│   ├── Channels
│   ├── Conversations and Handover
│   └── Actions
└── Business systems
    ├── Commerce domain
    ├── future workflow-proven domains
    └── external systems and providers
```

Agents are interaction actors. Business systems own authoritative state and operations. Actions connect an Agent to permitted work. External integrations connect AgentHub to systems outside its authority boundary.

## Problem, users and valid scenarios

AgentHub gives workspace owners, admins and operators one place to configure Agent behavior and immutable revisions, assign trusted Knowledge and authorized work, deploy through Channels, operate Conversations with AI/human handover and inspect real runtime state. External visitors or contacts interact through scoped channel identities. A user may belong to multiple workspaces.

Valid Agent scenarios include portfolio/personal, company website, spa/salon, clinic or other regulated service when its requirements are met, education, real estate, Commerce/shop, internal company, customer support, lead generation and future workflow-proven use cases.

### Portfolio Agent

A Portfolio Agent answers from a CV, biography, projects, skills and articles; receives contact requests; sends approved information or a CV; and may arrange a meeting. It must work with no product, inventory, Order, POS or Commerce Customer records.

### Company website Agent

A Company Agent explains services, qualifies a lead, collects permitted contact information, sends approved material, schedules a demo and hands the Conversation to sales.

### Service or appointment Agent

A spa or similar service Agent explains services and prices, checks authoritative availability, creates/reschedules/cancels appointments, sends confirmation and hands work to staff. Forms, Calendar and messaging may implement this outcome without becoming the user's product model.

### Commerce Agent and human operations

A Commerce Agent may search Catalog, resolve a variant, check Inventory, collect or identify a Customer, create an Order, obtain provider-backed payment status and support returns when those owning domains and actions exist. Human staff use the same authoritative Catalog, Inventory, Customer, Order and payment state through operational UI such as POS; the Agent is not an external chatbot beside a separate Commerce system.

### Internal assistant

A Company workspace operates an Agent over internal documents and approved internal systems without any Commerce dependency.

Every Platform/Core design must remain compatible with Knowledge-only, Commerce-enabled and internal-tool scenarios.

## Core concepts and ownership

| Concept | Product meaning |
|---|---|
| Workspace | Generic tenant and isolation boundary; not a permanent business type |
| Agent | Generic configurable actor with identity, lifecycle, revisions, assignments and operational state |
| Knowledge | Workspace-owned grounded content and lifecycle independent of Commerce |
| Action / Tool | Authorized typed entry to an owning domain or external service; never arbitrary model-side mutation |
| Channel | Delivery boundary such as Website, Facebook or Zalo |
| Conversation | Channel-normalized thread shared by AI and human operations |
| Contact | Cross-channel relationship identity; not automatically a Commerce Customer |
| Domain system | Authoritative entities, business rules and state, such as Commerce Catalog/Inventory/Orders |
| Workflow component | Supporting implementation such as structured input, document delivery, email, Calendar or webhook handling |

A workspace may use zero or more domain capabilities. Do not encode permanent `shop`, `portfolio`, `company` or `clinic` workspace types merely to choose functionality.

## Agents perform actions, not only chat

AgentHub must progress beyond `user -> LLM -> RAG -> answer`:

```text
user request
  -> Agent resolves identity, intent and Conversation context
  -> chooses trusted Knowledge or a permitted Action
  -> owning domain system or approved external service executes
  -> authoritative result/state is recorded
  -> Agent continues the Conversation or requests human help
```

Action foundations must emerge from real workflows. The first effectful Action introduces only the necessary typed input/output, validation, server-side authorization, workspace isolation, Agent permission, confirmation/approval, idempotency, execution status, retry policy, audit, traceability, provider reconciliation and safe error behavior. Model output never grants permission or directly mutates authoritative state.

Do not build a generic action platform, capability registry, integration framework or workflow engine and then search for a use case. Implement a complete real workflow, observe what truly repeats and extract the smallest reusable abstraction.

Controlled automation comes only after meaningful actions and events exist. It requires explicit scope, trigger, permission, audit, status, error/retry policy, pause/disable, user visibility and loop prevention.

## Current product

The completed roadmap sections 1 and 2, together with phases 3.1 and 3.3, provide:

- FastAPI-owned authentication, workspace membership and tenant isolation;
- one generic Agent model with draft configuration, immutable publication and pause/archive behavior;
- private Knowledge ingestion, immutable versions, freshness review, recovery, diagnostics, PostgreSQL-authoritative chunks and Qdrant retrieval;
- a substantial Commerce Catalog with generic products, variants, options, collections, locations, pricing, current nullable inventory and source-agnostic spreadsheet import;
- bounded grounded generation with conditional read-only Catalog tools;
- Website widget, visitor image input, Facebook Messenger and Zalo;
- normalized Conversations, durable delivery, unified Inbox and human handover;
- consent-aware Contacts/leads, operational analytics, usage limits, retention and redacted operations.

Agent defaults and runtime composition are domain-neutral: Catalog instructions and tools are exposed only when readable products exist in the server-authorized scope. Catalog scope naming and Commerce-first UI remain implementation debt, not universal product semantics.

## Commerce direction

Commerce remains the first large product domain and should grow toward complete human and Agent operation, including Catalog, multi-location Inventory, Orders, Customers, Pricing, Suppliers/Purchasing, Returns, POS, provider-backed payments and invoices, applicable receivables/payables, branches, loyalty, staff/shift operation and reports.

Catalog models must remain multi-industry. Generic options/attributes cannot be reduced to fashion-only `color` and `size`. Inventory preserves `NULL = unknown or unmanaged` and `0 = known out of stock`. Operational writes require auditable movements rather than unexplained quantity replacement. Important entities use lifecycle/archive semantics that preserve operational history.

Catalog import is source-agnostic: a user supplies CSV/XLS/XLSX data without first selecting Sapo, KiotViet, Shopify or a custom spreadsheet. Profiling, header/schema inference, mapping, preview, validation, normalization, staging, conflicts, diff and commit operate on the file's structure. Direct vendor connectors are separate future integrations.

Commerce may interleave with cross-domain work when it proves a real Agent Action, but it cannot define all of Platform/Core or block proof that AgentHub is general-purpose.

## Knowledge, Channels and lifecycle

Knowledge is an operational pillar, not merely a file-upload tab. Operators must be able to understand what an Agent knows, where it came from, whether processing succeeded, which version is active, how fresh it is and why retrieval may be degraded. PostgreSQL/Supabase remains authoritative; Qdrant is a filtered rebuildable index; OpenAI is the current real provider. Do not add unused providers for future-proofing.

Omnichannel Conversations and handover remain core product requirements independent of the current transport. Website, Playground, Facebook, Zalo and future Channels converge on the same Agent/Conversation meaning. Transport architecture must serve handover and operational requirements rather than remove them.

An Agent is more than `prompt + model`. Its lifecycle is:

```text
Create -> Configure -> Give Knowledge -> Grant abilities/domain access
       -> Test -> Publish -> Observe -> Improve
```

Publish must represent an immutable usable revision and increasingly expose meaningful readiness: instructions, required Knowledge, valid Channel configuration, connected Action providers and blocking failures. Full onboarding may come later, but useful guidance, validation and errors are required throughout earlier phases.

## Product decision filter

Every future phase and acceptance review asks:

- Does this preserve a general-purpose Agent platform rather than turn it into Commerce SaaS?
- Does the user think in terms of their goal rather than developer primitives?
- Does the Agent perform useful work rather than only return text?
- Is any abstraction being built before a real use case proves it?
- Does the domain model remain multi-industry rather than hardcode the MVP vertical?
- Is each fact presented once with a clear owner rather than duplicated across cards and panels?
- Is the UI returning to a generic CMS/dashboard template?
- Do human and Agent actors use the same authoritative domain state?
- Do sensitive actions have authorization, confirmation/approval where needed, idempotency and audit?
- Can regulated execution remain with a qualified integration provider while AgentHub owns UX, workflow, permitted operational state and audit?

## Non-goals and prohibited interpretations

- Making Commerce mandatory for Workspace or Agent creation, or concluding that Commerce is unimportant.
- Building every feature of a KiotViet-like system before improving the Agent.
- Treating Forms, Documents, Email, Calendar or Booking as unnecessary; they remain useful workflow components.
- Turning every component into a domain, module or menu.
- Treating “general-purpose” as permission for an early universal workflow engine.
- Treating World UI as a 3D game, decorative motion or replacement for accessible focused screens.
- Allowing Agent Actions to call arbitrary APIs or exceed server-authorized scope.
- Deferring correctness and tests to the centralized quality phase.
- Deferring useful guidance and error handling to the final onboarding phase.
- Treating payment or invoicing UX as permission for AgentHub to become an unapproved regulated provider.
- Treating RAG, Agent configuration, Qdrant or model prose as authoritative business state.
- Creating one Agent model per use case, one microservice per domain or unused provider implementations.
- Fabricating metrics, connection state, Agent state, people, products or activity to make the product look populated.
- Repository-wide renames or migrations for conceptual aesthetics; user-visible naming debt is fixed when a coherent approved experience requires it.

Delivery order and implemented/planned status live only in [`roadmap.md`](roadmap.md). Compliance boundaries live in [`compliance.md`](compliance.md); this product document is not legal advice.
