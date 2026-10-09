# Decision register

This file records owner-approved product and technology choices. Roadmap commitments live in [`roadmap.md`](roadmap.md); detailed behavior lives in domain and reference documents.

Status values are `Confirmed`, `Open` and `Superseded`.

## Confirmed product decisions

| Area | Decision |
|---|---|
| Product | AgentHub is a multi-tenant, omnichannel AI-agent platform |
| Initial vertical | Fashion-shop assistance is the first implemented vertical, not a permanent limitation of the core |
| Core channels | Website, Facebook Messenger and Zalo are product capabilities; Website is complete and Facebook/Zalo are the current delivery priority |
| Operating model | AI automation and human inbox/handoff share one normalized conversation system |
| Later deliveries | Agent quality, guided onboarding, data synchronization and SaaS commercialization will follow omnichannel operations |
| Commerce safety | Catalog consultation is read-only; autonomous orders, payments, refunds and stock mutation are not authorized |

## Confirmed technology decisions

| Area | Decision |
|---|---|
| Frontend | Next.js and TypeScript dashboard; independent TypeScript/Vite widget bundle |
| Backend | FastAPI and Python 3.12 |
| Database | Supabase PostgreSQL accessed server-side through SQLAlchemy 2 async and asyncpg |
| Migrations | Alembic; schema changes use migrations rather than manual production edits |
| Channel credential vault | Supabase Vault; application tables retain only opaque Vault UUID references and Supabase manages the per-project root key |
| Storage | Supabase Storage with private buckets for customer uploads and knowledge documents |
| Authentication | Custom FastAPI-owned email/password authentication; no Supabase Auth dependency |
| AI provider | OpenAI behind server-side generation, vision and embedding adapters |
| Retrieval | Qdrant is the rebuildable vector index; PostgreSQL owns authoritative documents, chunks and active generations |
| Agent orchestration | Simple bounded custom orchestration with typed tools; no framework dependency |
| Ingestion | Durable PostgreSQL jobs claimed by a dedicated worker with leases and fencing |
| UI foundation | Tailwind CSS and shadcn/ui conventions; only approved components are introduced |

## Confirmed data decisions

| Area | Decision |
|---|---|
| Tenant vocabulary | `workspace` is the tenant; `agent` is the domain entity |
| Identifiers | UUIDv7 for users/workspaces and externally addressed agent/conversation IDs; BIGINT identity for dense internal rows |
| Catalog | Generic options/attributes, locations and collections; structured CSV/XLS/XLSX MERGE import |
| Catalog truth | Current structured catalog owns price, SKU, options and stock; `NULL` remains unknown and differs from zero |
| Knowledge | Manual text and private PDF/TXT are implemented; catalog data is not embedded as the source of current stock/price |
| Contact capture | Optional, explicit, versioned consent; chat never requires contact details |
| Local retention | Visitor sessions/transcripts 24 hours, unattached images 30 minutes, attached images one hour, leads 30 days |
| Local quota | 1,000 generated turns per workspace-local month, shared by Widget and Playground |

## Open implementation and operating decisions

These choices do not reopen committed product scope:

- Exact OpenAI model IDs, embedding dimensions and production budgets.
- Zalo app/account prerequisites, token rotation, provider-specific message windows and supported payload subsets.
- Production retention periods, jurisdiction-specific privacy wording and processor disclosures.
- Email provider, production domains and backup objectives beyond the required Supabase Vault key-preservation procedure.
- External catalog/knowledge connector vendors and synchronization SLAs.
- Commercial plan structure, payment provider and billing rules for M3.

## Change control

An owner request may add or supersede a decision. Update this register, the affected domain document and the active task in the same change. Do not silently reinterpret a roadmap capability as optional, or treat an open implementation detail as permission to change the confirmed stack.

Superseded details remain available through Git history; they are not duplicated in the current documentation tree.
