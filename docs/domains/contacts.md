# Contacts and leads

## Function and ownership

A Contact is a workspace-level identity and customer-service relationship assembled from consented or provider-asserted channel evidence. A Lead is a consented follow-up event/state. Neither is automatically a Commerce Customer.

## CURRENT

- Website callback consent creates a contact identity and lead linked to trusted conversation/session ownership.
- First verified Facebook/Zalo inbound creates a distinct connection-namespaced provider identity.
- Search, cursor pagination, shared tags, assignment, role-aware detail, notes, conversation/lead history, and bounded CSV export.
- Exact normalized email/phone duplicate suggestions plus owner/admin, reasoned, version-checked, auditable, reversible logical merge.
- Purpose-based expiry of PII, identities, notes, tags, assignment, and merge reasons while content-free audit facts may remain.

Main data: contacts, identities, leads, notes, shared tag links, contact audit events, and merge events. Main surfaces: Contacts and Inbox-to-contact navigation.

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

Related authority: [`commerce.md`](commerce.md), [`conversations.md`](conversations.md), [`../security.md`](../security.md).
