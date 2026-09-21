# 12 — Full target-product scope (not MVP authorization)

## Product thesis
AgentHub lets individuals and organizations create knowledge-grounded AI assistants, connect them to messaging channels, manage contacts/conversations and add tightly controlled business tools. The first release solves website fashion-shop shopping assistance; portfolio, support, bookings and internal assistants are **later use cases**, not hardcoded assumptions about all agents.

## Actors
- Platform operator: maintains service, pricing/quotas, abuse response and cross-workspace administrative controls with auditable access.
- Workspace owner/admin/member: manages a tenant's agents, knowledge, catalog, channels, contacts and reports subject to role permissions.
- Website/social visitor: interacts with a published agent through a scoped channel session; may be anonymous where channel permits.
- Human operator: receives escalation and responds in a future live inbox.

## Capability map and delivery status
| Domain | Full product capability | First MVP slice | Follow-on |
|---|---|---|---|
| Identity | Signup, verification, reset, session revoke, membership, invitations, MFA eventually | Owner email/password, foundational RBAC | Invitations, MFA, richer audit |
| Workspace | Settings, domains, members, data policies, limits | One shop workspace; multi-tenant-safe model | Multi-workspace UX, organizations |
| Agents | Multiple agents, versions, channels, tools, publishing, analytics | Shop agent with controlled prompt/tools | Template library, schedules, workflow editor |
| Knowledge | Files, URL import, ingestion/re-indexing, citations, governance | FAQ, TXT/PDF and catalog; structured search + RAG | DOCX, crawl/sync, lifecycle policies |
| Conversation | Thread history, streaming, attachments, contacts, handoff | Website widget, image, lead, callback CTA | Unified inbox, staff assignment, SLA |
| Channels | Web, Facebook, Zalo, extensible adapters | Website | Official platform integration after review |
| Commerce | Catalog, variants, sizing, stock, product cards | Read-only grounded consultation, CSV/manual data | External commerce sync, order lookup, approved write actions |
| Other business tools | Calendar, ticketing, CRM, knowledge operations | None | Permissioned connectors per use case |
| SaaS | Plans, meter, quota, billing, invoices, limits | Internal usage record and safety cap | Paid plans/subscriptions |
| Operations | Health, logs, retries, backups, release controls | Local dev, focused QA | Docker on VPS, hardened operations |

## MVP must prove
A fashion shop can sign up, create/activate its workspace, upload shop knowledge and catalog, publish a website widget, provide accurate product/variant answers, process opt-in contact information, handle shopper images without leaking them to other tenants, and inspect conversation history. Prices/stock must be source-backed at query time; no AI-created orders or charges.

## Non-goals for the first release
No Facebook/Zalo live credentials, no automatic checkout/refunds, no subscription charging, no workflow canvas, no multi-provider model marketplace, no live staffed inbox, no scheduled website scraper, no VPS deployment requirement to finish the local MVP.

## Success measures (targets are not yet approved)
Grounded-answer accuracy, false stock/price claim rate, product-card click-through, unresolved/handoff rate, first-response latency, user-reported helpfulness, cost per conversation, tenant isolation defects. Baselines and numeric targets require a pilot, not invented values.

## Rules for future domains
The core concepts must not be named `shop_agent` or require a product catalog for every agent. Commerce-specific tools and screens live in the commerce module; knowledge- or portfolio-oriented agents may exist without commerce data. Paid or external-channel features each need their own security, permission, budget and legal reviews.
