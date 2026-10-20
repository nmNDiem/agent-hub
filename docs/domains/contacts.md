# Contacts and leads

## Function and ownership

A Contact is a workspace-level identity and customer-service relationship assembled from consented or provider-asserted channel evidence. A Lead is a consented follow-up event/state. Neither is automatically a Commerce Customer.

## CURRENT

- Website callback consent creates a contact identity and lead linked to trusted conversation/session ownership.
- An explicit conversational follow-up request can create or reuse one Lead per Conversation through the Contacts-owned `contacts.follow_up.request` service. Website requires email or phone; Facebook/Zalo use the already verified, connection-scoped provider Contact identity without fabricated Website data.
- A published Agent may finalize one complete immutable structured-intake submission per Conversation through `contacts.intake.submit`. The service validates stable keys and typed values against the revision snapshot; Website requires submitted email or phone and Facebook/Zalo reuse only verified provider identity.
- Structured-intake Leads begin at human-owned `pending_review`. Owner/admin operators may version-safely choose `qualified` or `not_qualified` with actor/time attribution; model output and answers cannot set qualification.
- Narrow action execution evidence records server-bound Agent revision, Conversation, source message, request hash, safe outcome/status and timing without copying messages, PII, provider IDs, prompts or raw tool arguments.
- First verified Facebook/Zalo inbound creates a distinct connection-namespaced provider identity.
- Search, cursor pagination, shared tags, assignment, role-aware detail, notes, conversation/lead history, and bounded CSV export.
- Exact normalized email/phone duplicate suggestions plus owner/admin, reasoned, version-checked, auditable, reversible logical merge.
- Purpose-based expiry of PII, identities, notes, tags, assignment, and merge reasons while content-free audit facts may remain.

Main data: contacts, identities, leads, finalized intake submissions, action-specific execution evidence, notes, shared tag links, contact audit events, and merge events. Main surfaces: Contacts, Leads and Inbox-to-contact navigation.

## Core flow

Receive verified identity/consent evidence → resolve only under documented exact rules → create or link the Contact → expose permitted profile/timeline → allow authorized assignment/notes/tags → merge only through reviewed exact-identity evidence → expire by source purpose.

## Invariants

- Never merge by display name or model inference.
- Client-supplied workspace/conversation ownership is not trusted.
- PII is role-restricted, absent from routine logs, and not echoed from public creation APIs.
- Merge/link operations retain safe evidence and a reversal path.
- Provider identity uniqueness is scoped to its connection/workspace.

## APPROVED DIRECTION

If Commerce introduces Customer, define an explicit, auditable promotion/link from Contact to Customer. The Commerce aggregate owns purchasing identity, addresses, tax/commercial policy, and order history; Contact remains the communication identity.

## NOT IMPLEMENTED

No Commerce Customer, loyalty profile, marketing audience engine, or probabilistic identity resolution exists.

## Change trigger

Introduce Customer only with the first transactional Commerce workflow that needs durable purchasing identity; define consent, duplicate handling, retention, and link/reversal rules first.

## Dependencies and conditional references

- Conversation linkage belongs to [`conversations.md`](conversations.md); future Customer promotion is bounded by [`commerce.md`](commerce.md).
- Load [`../security.md#tenant-owned-data`](../security.md#tenant-owned-data) for identity/PII authorization or retention changes.

## Relevant code paths

- `apps/api/src/agent_hub_api/contacts/`
- `apps/api/src/agent_hub_api/leads/`
- `apps/web/src/features/contacts/`
- `apps/web/src/features/leads/` only for lead workflow compatibility
