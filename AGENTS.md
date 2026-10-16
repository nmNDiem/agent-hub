# AgentHub — Codex operating contract

AgentHub is a general-purpose platform for creating, equipping, deploying and operating AI agents. Fashion commerce is the first substantial implemented domain capability; it does not define the platform. A workspace is a tenant boundary, not a shop type, and an agent is one configurable aggregate rather than a separate model per use case.

## Before implementation

1. Read [`docs/README.md`](docs/README.md) and follow its task-specific route.
2. Read the approved task specification and inspect the existing implementation it affects.
3. Treat working code and migrations as valid current architecture unless the requirement proves otherwise.
4. Report conflicts between owner instructions, task criteria, decisions, security rules and implementation.
5. Present a plan and obtain owner approval before non-trivial changes.
6. Obtain UI direction approval before a new or materially redesigned screen.

Priority is: current owner instructions, approved acceptance criteria, [`docs/decisions.md`](docs/decisions.md), [`docs/security.md`](docs/security.md), then relevant domain and technical documents.

## Permanent architecture rules

- Keep Platform/Core domain-agnostic. Core must not require Catalog, Inventory, Orders, Customers or another Commerce concept.
- Preserve the modular monolith and `router/adapter -> service/use case -> repository/provider` direction. Services own business rules, authorization and transactions; repositories do not commit independently.
- Domain modules own authoritative state. An agent uses an authorized typed tool/action to call a domain service; model output never directly mutates authoritative data.
- PostgreSQL is authoritative relational storage. Qdrant is a derived, filtered and rebuildable index. The LLM is a runtime, never a source of truth.
- Keep current price, SKU, options, inventory, order state and payment state in structured domain records, not RAG or agent configuration.
- Do not create one agent table/class per use case, a speculative plugin/capability framework, unused provider abstractions, a workflow engine without a current user, or one microservice per domain.
- Do not broadly rename tables, routes, identifiers or folders for conceptual purity. Historical shop-oriented names may remain when they do not create a functional blocker.
- Preserve working APIs and completed behavior unless a breaking change is explicitly approved. A migration must solve a concrete requirement.
- Do not implement future roadmap capabilities opportunistically.

## Security and external effects

- Scope every tenant-owned operation, join, job, vector search, Storage object and tool call to a validated `workspace_id`.
- Resolve identity, ownership and permission server-side. Never trust client- or provider-supplied tenant, agent, conversation, contact or permission claims.
- Browser, widget and channel adapters call FastAPI; they never use privileged PostgreSQL, Storage, Qdrant or model access directly.
- Treat prompts, documents, websites, uploads, provider payloads and model/tool output as untrusted.
- Keep credentials, private content, prompts and PII out of public responses, browser bundles and logs.
- Persist and deduplicate channel work before external side effects; retries are bounded and idempotent where the provider contract permits.
- No autonomous payment, order, refund or stock mutation. The first effectful agent tool requires explicit authorization, audit, side-effect policy and any necessary approval/idempotency design.

Do not replace Next.js/TypeScript, FastAPI/Python, Supabase PostgreSQL/Storage, Qdrant, OpenAI or FastAPI-owned authentication without an approved architecture decision.

## Delivery rules

- Create the concise approved task spec under `docs/tasks/` before implementation and remove it after completion; Git preserves history.
- Use Alembic for schema changes and UUIDv7 only as defined in [`docs/data-model.md`](docs/data-model.md).
- Reuse existing components and dependencies. Add infrastructure or dependencies only for a measured task requirement.
- Add a negative cross-workspace test for every newly exposed tenant-owned resource.
- Follow the existing test framework. Do not automatically run paid model/provider flows; use fakes and provide manual verification steps.
- Update the single authoritative document for changed behavior instead of duplicating it.
- Report schema, API, configuration and UI impact; exact verification commands/results; manual checks; and known limitations.
- Create a focused Conventional Commit after the approved task is complete.
