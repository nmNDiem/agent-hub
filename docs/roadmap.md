# Delivery roadmap

The roadmap sequences capabilities already defined in [`product.md`](product.md). A later delivery is still part of the product. Each implementation task requires an approved task spec, acceptance criteria and focused commit; that gate refines execution rather than reconsidering whether the roadmap capability belongs in AgentHub.

Status values: `Complete`, `Current`, `Later`.

## Completed foundation — F0-F5

Status: **Complete**

| Delivery | Outcome |
|---|---|
| F0 Foundation | Repository, API/dashboard/widget skeleton, configuration, CI, migrations and local boot |
| F1 Identity and tenancy | Custom authentication, sessions, workspaces, membership and tenant boundaries |
| F2 Catalog | Products, variants, options, locations, collections, images and universal CSV/XLS/XLSX import |
| F3 Knowledge and agents | Private ingestion, OpenAI/Qdrant adapters, grounded runtime, typed tools and Playground |
| F4 Website widget and vision | Publishing, anonymous scoped sessions, SSE, product cards and visitor image flow |
| F5 Local operations | Consented leads, conversation history, dashboard usage/quota, retention and observability |

Detailed F0-F5 implementation history and verification evidence are preserved under [`archive/`](archive/). They are not active roadmap documents.

## M1 — Omnichannel Operations

Status: **Current**

Goal: operate Website, Facebook Messenger and Zalo conversations through one secure conversation, contact and human-service workflow.

### M1.1 Shared channel foundation

- Normalized inbound/outbound contracts and capability-aware rendering.
- Channel connections and encrypted credential lifecycle.
- Verified webhooks, deduplication, ordering and bounded retries.
- Durable outbound delivery state and provider-safe failure handling.
- Contact/channel identity mapping without trusting provider payload tenancy.

### M1.2 Facebook Messenger

- Page connection and revocation flow.
- Verified inbound messages and supported attachments.
- Outbound delivery through the shared pipeline.
- Connection health, reauthorization and real failure states.

### M1.3 Zalo

- Official-account connection and revocation flow.
- Verified inbound messages and supported attachments.
- Outbound delivery through the shared pipeline.
- Zalo-specific constraints isolated inside its adapter.

### M1.4 Unified inbox and human handoff

- Website/Facebook/Zalo threads in one inbox.
- Explicit AI/human ownership and takeover/resume behavior.
- Reply composer, unread state, assignment, status, notes and tags.
- Delivery state, retry visibility and role-aware access.

### M1.5 Customer and lead timeline

- Consent-aware contact profiles and channel identities.
- Conversation/lead timeline, notes, tags and assignee.
- Safe identity linking/merging with audit and reversal rules.
- Retention and export rules for contact data.

### M1.6 Operational analytics

- Conversation and response activity by channel and agent.
- AI/human resolution and handoff measures.
- Lead conversion, product interest and unresolved conversation signals.
- Definitions based on persisted events; no invented cost or business uplift.

M1 task specs are created one at a time in [`tasks/`](tasks/) and must preserve the boundaries in [`reference/channels.md`](reference/channels.md).

## M2 — Product Intelligence and Experience

Status: **Later**

- Agent evaluation, feedback, unresolved-question review and regression cases.
- Version comparison, controlled rollout and quality analytics.
- Guided onboarding, setup checklist and publish readiness.
- Website/knowledge synchronization and source freshness management.
- Catalog connector synchronization, reconciliation and freshness policy.

## M3 — SaaS Commercialization

Status: **Later**

- Workspace invitations and richer role administration where not delivered in M1.
- Plans, entitlements and commercial quotas.
- Subscriptions, billing, invoices and signed payment webhooks.
- Platform operator controls, auditable support and account lifecycle.

## Out of committed scope

- Autonomous payments, refunds, order placement or stock mutation by an LLM.
- A drag-and-drop workflow canvas.
- Unrestricted arbitrary-code tools or arbitrary URL fetching.
