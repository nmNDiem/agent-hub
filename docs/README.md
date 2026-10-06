# AgentHub documentation

This directory is the single entry point for product and engineering guidance. AgentHub is a multi-tenant, omnichannel AI-agent platform. The completed foundation is a fashion-shop assistant with a website widget; the current delivery focus is Facebook, Zalo and the operating workflows around those channels.

## Current state

- F0-F5 are complete: identity and tenancy, catalog/import, knowledge/RAG, grounded agent runtime, Playground, website widget/vision, leads, read-only conversations, usage/quota, retention and local operations.
- The current delivery is **M1 Omnichannel Operations**: shared channel infrastructure, Facebook Messenger, Zalo, unified inbox, customer/contact timeline and operational analytics.
- Agent quality, guided onboarding, automatic knowledge/catalog synchronization and SaaS commercialization are committed later deliveries.
- Deployment is an operational track, not a condition for defining the product or sequencing product capabilities.

## Document map

| Question | Authoritative document |
|---|---|
| What product are we building? | [`product.md`](product.md) |
| What has the owner decided? | [`decisions.md`](decisions.md) |
| How is the system shaped? | [`architecture.md`](architecture.md) |
| What security rules are mandatory? | [`security.md`](security.md) |
| What is being delivered next? | [`roadmap.md`](roadmap.md) |
| How does a business domain behave? | [`domains/`](domains/) |
| What are the concrete technical contracts? | [`reference/`](reference/) |
| How should the UI behave? | [`design/README.md`](design/README.md) |
| How is the system run locally? | [`operations/`](operations/) |
| What task is currently approved? | [`tasks/`](tasks/) |
| Why was an old choice made? | [`archive/`](archive/) |

## Reading routes

Read only the route relevant to the task; do not load the whole documentation tree.

| Work type | Read first | Then read |
|---|---|---|
| Any code change | `decisions.md`, `architecture.md`, `security.md` | Active task spec |
| Identity or membership | `domains/identity-workspaces.md` | `reference/data-model.md`, `reference/api.md` |
| Agent/RAG/vision | `domains/agents.md`, `domains/knowledge.md` | `reference/agent-runtime.md` |
| Catalog/import | `domains/catalog.md` | `reference/data-model.md`, `reference/api.md` |
| Facebook/Zalo/widget | `domains/channels.md`, `domains/conversations.md` | `reference/channels.md`, `reference/api.md` |
| Inbox/contact/lead | `domains/conversations.md`, `domains/contacts.md` | data model, API and relevant design screen |
| Analytics or billing | corresponding domain file | data model, API and testing reference |
| Frontend/UI | relevant domain file | `reference/frontend.md` and relevant design file |
| Operations | `operations/local-development.md` or `operations/local-pilot.md` | security and testing reference |

## Authority and vocabulary

Current canonical documents override archived material. Within current documentation: owner decisions and task acceptance criteria come first, then security invariants, domain behavior, technical references and design guidance. If two current files disagree, stop and fix the documentation conflict rather than choosing silently.

`workspace` is the tenant and may be presented as a shop in the fashion UI. `agent` is the domain entity and may be presented as a chatbot. `channel` is a delivery connection such as Website, Facebook Messenger or Zalo. Do not create parallel persistence concepts named `shop` or `bot`.

## Archive policy

[`archive/`](archive/) preserves ADRs, completed F0-F5 plans, verification notes and the superseded documentation layout. It is not current implementation guidance and must not be read by default. Consult it only when the current docs explicitly link to a historical decision or a task requires implementation history.
