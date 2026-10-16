# Product

Load this authority when defining product meaning, users, permanent scenarios or non-goals. Routine implementation should rely on its phase and domain packet instead.

## Definition

AgentHub is a general-purpose platform for creating, configuring, equipping, deploying and operating AI agents. It combines knowledge-grounded reasoning, controlled tools, channels, conversations, human operations and observable runtime behavior inside a workspace tenancy boundary.

AgentHub is not a POS product with AI attached, not a commerce-only system and not only a chatbot builder. Fashion commerce is the first substantial implemented domain capability and remains a major product direction, but Platform/Core must work without Commerce.

## Problem and users

AgentHub gives individuals and organizations one place to:

- configure agent behavior and immutable published revisions;
- attach trusted Knowledge and, when available, authorized domain tools;
- deploy through Website and messaging Channels;
- operate normalized conversations with AI/human handoff;
- preserve tenant isolation, auditability and authoritative domain state.

Primary actors are workspace owners/admins, workspace members/operators, external visitors or contacts, and least-privilege platform operators. A user may belong to multiple workspaces.

## Core concepts

| Concept | Product meaning |
|---|---|
| Workspace | Generic tenant and isolation boundary; not a permanent business type |
| Agent | Generic configurable runtime aggregate with lifecycle and published revisions |
| Knowledge | Workspace-owned grounded content independent of Commerce |
| Tool / Action | Authorized typed entry to a domain service; never arbitrary model-side mutation |
| Channel | Delivery boundary such as Website, Facebook or Zalo |
| Conversation | Channel-normalized thread shared by AI and human operations |
| Contact | Cross-channel relationship identity; not automatically a Commerce Customer |
| Domain capability | Optional authoritative business functionality such as Commerce, CRM or Booking |

A workspace may use zero or more domain capabilities. Do not encode a permanent `shop`, `portfolio`, `company`, `clinic` or similar workspace type merely to choose functionality.

## Permanent architecture scenarios

### Portfolio Agent

A Personal Portfolio workspace publishes an Agent that answers from CV, biography, projects, skills and articles through a Website embed and can expose an approved contact or CV action. It must function with no products, locations, inventory, orders, POS or Commerce customer records.

### Commerce workspace

A Fashion Shop workspace may operate Sales, Support and Operations Agents with Knowledge, Catalog, Inventory, Orders, Contacts/Customers, Purchasing, payment integrations, analytics and eventually POS. Agents reach these domains only through authorized tools and services.

### Internal assistant

A Company workspace operates an Agent over internal documents and approved internal tools/workflows without any Commerce dependency.

Every platform-level design must remain compatible with all three scenarios.

## Current product

The completed F0-F5 and M1 deliveries provide:

- FastAPI-owned authentication, workspace membership and tenant isolation;
- one generic Agent model with draft configuration, immutable publication and pause/archive behavior;
- private Knowledge ingestion, PostgreSQL-authoritative chunks, Qdrant retrieval and citations;
- a substantial Commerce Catalog with products, variants, options, collections, locations, pricing, current inventory and import;
- bounded grounded generation with read-only Catalog tools;
- Website widget and visitor image input;
- Facebook Messenger and Zalo channel adapters;
- normalized conversations, durable delivery, unified inbox and human handoff;
- consent-aware Contacts/leads and operational analytics;
- usage limits, retention and redacted operations.

Current agent runtime defaults, Catalog scope and much of the UI remain commerce-oriented first-vertical coupling. They are not universal platform semantics.

## Approved direction

- Platform/Core remains domain-agnostic.
- Agent behavior comes primarily from configuration, assigned Knowledge, authorized Tools, policies and Channels—not separate foundational agent types.
- Domain modules remain authoritative for their own state.
- Commerce expands as an optional first-class domain; CRM, Booking, Forms, Email/Calendar, Documents, Projects, HR, Education and custom systems are future possibilities, not implemented commitments.
- High-impact actions must support authorization, attribution, audit and approval where appropriate.
- Regulated functions integrate with qualified external providers unless a separate product, legal, security and architecture decision authorizes otherwise.

## Non-goals

- Making Commerce mandatory for workspace or agent creation.
- Creating one agent model per use case.
- Treating RAG, agent configuration or LLM prose as authoritative business state.
- A speculative plugin registry, universal service locator or unused workflow engine.
- One microservice per domain without an operational requirement.
- Autonomous payment, refund, order or stock mutation under the current authorization model.
- Wallet, stored-value, custody, lending, credit or unlicensed payment intermediation.
- A generic CRUD/CMS interface where every table becomes navigation.
- Repository-wide renames or migrations for architectural aesthetics.

Delivery order and implemented/planned status live only in [`roadmap.md`](roadmap.md).
