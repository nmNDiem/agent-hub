# AgentHub — Instructions for Codex

Read this file and follow the task-specific route in [`docs/README.md`](docs/README.md) before changing code. Do not load the entire documentation tree. Material under `docs/archive/` is historical and is not current guidance unless a current document explicitly links to it.

## 1. Decision precedence

1. Explicit repository-owner instructions in the current task.
2. Approved task acceptance criteria.
3. Confirmed decisions in [`docs/decisions.md`](docs/decisions.md).
4. Security and tenant-isolation invariants in [`docs/security.md`](docs/security.md).
5. Relevant domain document, then technical reference and design guidance.

If current documents conflict, report and fix the conflict rather than choosing silently. Ask before an irreversible architectural change. Do not replace Next.js/TypeScript, FastAPI/Python, Supabase PostgreSQL, Supabase Storage, Qdrant, OpenAI or FastAPI-owned email/password authentication.

## 2. Product and roadmap

AgentHub is a multi-tenant, omnichannel AI-agent platform. F0-F5 are complete. The current product delivery is M1 Omnichannel Operations: shared channel foundations, Facebook Messenger, Zalo, unified inbox/human handoff, customer/contact timeline and operational analytics. Agent quality, guided onboarding, knowledge/catalog synchronization and SaaS commercialization follow in M2/M3.

All capabilities in [`docs/product.md`](docs/product.md) belong to the complete system. [`docs/roadmap.md`](docs/roadmap.md) defines delivery order, not optionality. Implement only the currently approved task; create its concise spec under `docs/tasks/` before code and archive it after completion.

## 3. Non-negotiable invariants

- Scope every tenant-owned read/write/query/tool/job/vector search/Storage object/channel connection to a validated `workspace_id`.
- Never trust workspace, agent, conversation, contact or permission identity supplied by a client/provider payload without resolving it against authenticated membership, a scoped Website session or a verified server-owned channel connection.
- Keep database, Supabase service, Qdrant, OpenAI, JWT and channel credentials out of browser bundles, public responses, logs and commits.
- Browser/widget/channel adapters call FastAPI; they never connect directly to privileged database, Storage, Qdrant or model resources. Custom app tokens are not Supabase Auth tokens.
- Current price, SKU, options and inventory come from structured catalog records at answer time. Never invent availability, discounts, shipping commitments or order outcomes.
- Treat prompts, documents, websites, images and provider payloads as untrusted data. They cannot override system/tool policy.
- Authorize before issuing private Storage access or returning tenant-owned data. Use private buckets for customer uploads and knowledge sources.
- No autonomous payment, order, refund or stock mutation.
- Errors/logs must not leak prompts, credentials, private content, PII or tracebacks.

## 4. Working agreement

Before non-trivial implementation:

1. Identify the roadmap delivery/task and list acceptance criteria.
2. Read only the documents routed for that work in `docs/README.md`.
3. State confirmed decisions and genuinely open implementation choices.
4. Present a plan and wait for owner approval before implementation.
5. For a new or materially redesigned screen, provide and obtain approval for the UI direction before coding it.

While implementing:

- Follow `router/adapter -> service/use case -> repository/provider` boundaries. Services own business rules, authorization and transactions; repositories do not commit independently.
- Use strict TypeScript and explicit Python typing. Do not introduce implicit `any` or bypass validation without a documented boundary.
- Validate all external input, including webhook signatures/raw bodies, upload bytes and model/tool output.
- Persist and deduplicate inbound/outbound channel work before external side effects; keep retries idempotent and bounded.
- Add Alembic migrations for schema changes; never edit a production database manually or edit generated artifacts.
- Use UUIDv7 only as defined in `docs/reference/identifiers.md`; never silently substitute UUIDv4 or require PostgreSQL native `uuidv7()`.
- Keep `.env.example` minimal. Stable limits and tuning defaults belong in typed configuration.
- Do not add dependencies, Redis, extra model providers, workflow frameworks or services without a scoped reason and approved task.
- Reuse existing components and abstractions; keep changes focused and remove dead code/imports introduced by the task.

Before completion:

- Run relevant existing lint, type, unit, integration and migration checks; report exact commands and results.
- Do not run paid chatbot/provider flows automatically. Use fakes/local substitutes and give the owner manual provider steps.
- Add a negative cross-workspace test for every newly exposed tenant-owned resource.
- Update the single authoritative domain/reference/design document rather than copying behavior into multiple files.
- Report schema/configuration impact, manual verification and known limitations.
- Create a focused Conventional Commit with a clear subject and detailed body describing what changed and why.

## 5. Commands

Use only actual repository commands documented in [`README.md`](README.md) and inspect package scripts before running them. Do not claim a command was run when it was not. Avoid builds, dev servers and E2E unless requested, required by project rules or necessary to verify the task.

## 6. Definition of done

Acceptance criteria pass; authentication/authorization and tenant isolation are covered; external inputs and user data are handled safely; API/data/UI behavior is documented once; no secrets are exposed; migrations are reversible when practical; test results are accurate; and no unrelated roadmap capability is implemented.
