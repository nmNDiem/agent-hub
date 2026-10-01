# 00 — Decision register

Status terms: **CONFIRMED** = explicitly selected by owner; **PROPOSED** = recommended design, owner has asked for recommendation, not a confirmed stack selection; **DEFERRED** = not in first MVP.

| Area | Decision | Status | Notes |
|---|---|---|---|
| Repository / product | `agent-hub` / AgentHub | CONFIRMED | |
| Product direction | Multi-tenant omnichannel AI-agent platform | CONFIRMED | Different business use cases later |
| First MVP | Fashion-shop AI assistant | CONFIRMED | Supersedes portfolio MVP |
| First channel | Website chat widget | CONFIRMED | Facebook/Zalo later |
| Backend | FastAPI + Python | CONFIRMED | |
| Database | Supabase PostgreSQL | CONFIRMED | Supabase is DB host, not an auth requirement |
| Storage | Supabase Storage | CONFIRMED | |
| Authentication | FastAPI-owned email + password | CONFIRMED | No Supabase Auth; standard password security mandatory |
| Frontend | Next.js + TypeScript | CONFIRMED | Dashboard; widget packaging separate design question |
| ID strategy | UUIDv7 selectively + BIGINT IDENTITY for internal rows | CONFIRMED | UUIDv7 for users/workspaces and required public IDs, **not** every PK; see `architecture/identifiers.md` |
| Domain naming | `workspace` tenant; `agent` domain entity, presented as shop/chatbot in UI | PROPOSED | Keep original API/schema vocabulary; no parallel `shops`/`bots` tables |
| UI components | Tailwind CSS + shadcn/ui conventions | CONFIRMED | Add only the component primitives required by approved work |
| ORM / migrations | SQLAlchemy 2 async + Alembic | CONFIRMED | PostgreSQL driver is asyncpg |
| Foundation runtimes | Python 3.12, Node.js 24, pnpm workspace | CONFIRMED | Pinned in repository configuration |
| Widget foundation | Independent TypeScript/Vite package scaffold | CONFIRMED | Package boundary only; functional embed/chat remains deferred |
| Retrieval | Qdrant vector index + Postgres structured search | CONFIRMED | Postgres owns documents/chunks/jobs; Qdrant is a rebuildable derived index with mandatory tenant filters |
| Qdrant development runtime | Non-production Qdrant Cloud cluster | CONFIRMED | Credentials stay server-only; integration tests use isolated randomly named collections and delete only their own collection |
| LLM provider | OpenAI | CONFIRMED | Server-side calls from FastAPI; exact model IDs are configurable |
| Embedding provider architecture | Provider-neutral adapter; OpenAI is the initial MVP implementation | CONFIRMED | Persist provider/model/dimensions/revisions; other providers require a separately approved task |
| OpenAI model IDs | Chat/vision/embeddings chosen by capability, price and testing | PROPOSED | Record deployed model IDs; no shop-owner choice in MVP |
| Agent framework | Simple custom bounded orchestration | CONFIRMED | F3.4; typed tools and server-validated final output, no framework dependency |
| Agent response contract | Channel-neutral conversational text plus server-validated structured evidence | CONFIRMED | Product facts remain structured so Web and future social adapters can render them without making the core runtime channel-specific |
| Async ingestion | PostgreSQL-backed durable jobs processed by a dedicated Python worker process | CONFIRMED | Fenced leases, heartbeat, classified retry and reconciliation; no Redis dependency for MVP |
| Multiple knowledge bases per agent | Yes at schema and API level | CONFIRMED | Workspace-scoped many-to-many assignment; catalog facts remain structured |
| LLM choice by shop owner | Not exposed in first MVP | PROPOSED | Server-configured provider/model |
| Agent tools | Read-only catalog/stock + opt-in lead capture | PROPOSED | Tools use explicit tenant context |
| Drag-and-drop workflow builder | After MVP | DEFERRED | |
| Account in multiple workspaces | Yes in schema | PROPOSED | Minimal first UI |
| Multiple agents per workspace | Yes in schema | PROPOSED | One published website agent initially |
| Roles | Owner/Admin/Member model; initially expose owner-focused UI | PROPOSED | Every action checked server-side |
| Billing / subscriptions | After MVP | DEFERRED | Track internal usage now |
| Widget branding | Color, avatar, position, greeting | PROPOSED | |
| Anonymous visitor chat | Yes, scoped anonymous session | PROPOSED | Rate limits and origin controls |
| Capture visitor contact | Optional with consent | PROPOSED | Email/phone are not prerequisites to chat |
| Human handoff | Contact CTA / callback lead, not live-agent inbox | PROPOSED | Live inbox deferred |
| Knowledge sources | Manual shop text and PDF/TXT documents; catalog remains structured data | CONFIRMED | No OCR for scanned or encrypted PDFs; catalog uses the confirmed structured importer |
| Catalog architecture | Generic options and a structure-driven CSV/XLS/XLSX importer | CONFIRMED | F2.1; no vendor-specific parser, default import mode is MERGE |
| DOCX and scheduled website crawling | After MVP | DEFERRED | |
| Source references | Product link/card and doc references when available | PROPOSED | Never fabricate citations |
| Upload and usage quotas | Server-enforced workspace limits and rate windows | CONFIRMED | Initial knowledge defaults are recorded in ADR F3.2 and remain deployment-overridable |
| Customer image input | Basic vision analysis + catalog matching | PROPOSED | Not specialized image-to-image search |
| Orders/payments/refunds | No execution in MVP | DEFERRED | Read-only integrations later if approved |
| Current runtime | Local development only | CONFIRMED | Do not claim VPS deployment or require Docker for day-one boot |
| Future runtime | Docker containers on VPS | CONFIRMED | Prepare deployable boundaries, but deploy in a later phase |

## Open decisions to validate at scaffolding or deployment
- Email delivery provider, exact OpenAI chat/vision/embedding model IDs, embedding dimensions and exact monthly usage limits.
- Future live-commerce connector/provider, stock refresh policy and connector identity mapping; manual CRUD plus CSV/XLS/XLSX MERGE is already the confirmed file-import baseline.
- User data retention periods, privacy notice, handoff destination, allowed domains and production secrets management.
- Local connection strategy for Supabase services: use a remote development Supabase project or explicitly provision local equivalents; no live customer data in dev.
- Future Qdrant production placement and backup policy; development uses the confirmed non-production Qdrant Cloud cluster.
- VPS provider, sizing, reverse proxy, domain, SMTP provider and backup location when production deployment is scheduled.

## Implementation status
The owner selected **local execution now** and **Docker-on-VPS later**. Infrastructure readiness in the MVP means documenting local startup, not claiming production deployment. The global product specification is in `docs/12-full-product-scope.md` onward; implementing those future modules requires a scoped task.

Do not treat the above open decisions as already selected. Configurable defaults and clear seams are preferred.
