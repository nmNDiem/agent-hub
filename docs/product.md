# Product

## Product thesis

AgentHub lets organizations create knowledge-grounded AI assistants, connect them to customer channels, operate conversations and contacts, and add controlled business tools. The first vertical is fashion commerce, but the core agent, channel, conversation and knowledge models must not require a product catalog for every use case.

The product is not merely a website chatbot. The complete system combines AI automation with human operations across Website, Facebook Messenger and Zalo.

## Users

- **Workspace owner/admin:** configures agents, knowledge, catalog, channels, staff access and business policies; monitors conversations, contacts and performance.
- **Workspace member/operator:** handles assigned conversations and contacts within granted permissions.
- **Visitor/customer:** communicates through Website, Facebook or Zalo, receives grounded answers and product suggestions, and may consent to contact follow-up.
- **Platform operator:** manages plans, quotas, abuse response and platform operations without unrestricted access to customer content by default.

## Product capabilities

| Domain | Complete product capability |
|---|---|
| Identity and workspaces | Email/password accounts, sessions, workspaces, invitations, roles and permissioned membership |
| Agents | Multiple agents, editable drafts, immutable published versions, tools, policies, evaluation and quality improvement |
| Knowledge | Manual content, private files, citations, ingestion/re-indexing, website sources and controlled synchronization |
| Catalog | Products, variants, generic options/attributes, locations, collections, current price/inventory and external synchronization |
| Channels | Website widget, Facebook Messenger and Zalo through a shared channel contract |
| Conversations | Normalized threads, AI processing, unified inbox, human handoff, assignment, status, notes, tags and delivery state |
| Contacts | Anonymous visitors, consented leads, channel identities, customer profiles and interaction timeline |
| Analytics | Usage, channel activity, response time, AI/human resolution, conversion, product interest and agent quality |
| Platform | Plans, entitlements, quotas, subscriptions, billing, invoices and operator controls |

These are parts of one product. The roadmap controls delivery order; it does not turn later capabilities into optional add-ons.

## Completed foundation and omnichannel operations

F0-F5 provide a working local fashion-shop vertical:

- FastAPI-owned authentication, workspace membership and tenant isolation;
- structured catalog, variants, locations, collections, images and CSV/XLS/XLSX import;
- private knowledge ingestion, Qdrant retrieval and grounded OpenAI runtime;
- agent configuration, Playground, publishing and embeddable website widget;
- text and image conversations with authoritative product cards;
- consented leads, safe contact handoff and read-only conversation history;
- basic dashboard usage, shared generation quota, retention and redacted operations.

This foundation proves the core data and AI boundaries. It is not the final depth of the operational product.

M1 adds shared Website/Facebook/Zalo channel operations, durable delivery, a unified human inbox,
consent-aware contact timelines and workspace-scoped operational analytics from persisted facts.

## Product outcomes

- A business can connect its customer channels without creating separate silos.
- AI answers remain grounded in workspace-owned knowledge and authoritative structured facts.
- A human can take over, assign and resolve work without losing channel history.
- A contact has one understandable timeline across consented identities and conversations.
- Owners can see whether agents and channels produce useful business outcomes.
- The platform can add new agent types and tools without weakening tenant isolation or making commerce mandatory.

## Product principles

1. **One conversation core, multiple channels.** Provider payloads are normalized at adapters; business logic is not duplicated per channel.
2. **Structured facts outrank model prose.** Price, SKU, options and inventory come from current catalog records.
3. **AI and human work are one workflow.** Handoff is a state transition, not a disconnected callback form.
4. **Consent and least privilege are defaults.** Identity, contact data and channel credentials are collected and exposed only when justified.
5. **Quality is observable.** Unknowns, failed deliveries, unresolved questions and human takeovers must become measurable signals.
6. **Later does not mean optional.** Committed product domains remain visible in the target model even when delivered after the current phase.

## Explicit boundaries

- No autonomous payment, refund, order placement or stock mutation without a separately designed authorization and confirmation model.
- No model-generated claim may override authoritative catalog or policy data.
- No channel is described as connected until its provider credentials and webhook/delivery checks succeed.
- No drag-and-drop workflow builder is required for the committed M1-M3 deliveries.
- Provider-specific limitations are respected; feature parity across Website, Facebook and Zalo is not assumed.
