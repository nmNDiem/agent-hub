# AgentHub — Instructions for Codex

> Read this file and the relevant documents in `docs/` before changing code. This repository starts as a **Fashion Shop AI Assistant MVP** and is designed to evolve into a multi-tenant, omnichannel AI-agent platform.

## 0. Decision precedence
1. Explicit instructions from the repository owner in the current task.
2. Confirmed decisions in `docs/00-decisions.md` and acceptance criteria for the task.
3. Security and tenant-isolation invariants in `docs/08-security.md`.
4. For ID implementation use `docs/architecture/identifiers.md`; for detailed UI use `docs/design/` and reference screenshots; for granular backend implementation use `docs/architecture/`. Numbered master docs remain authoritative if two guides conflict. Roadmap labels and sequencing belong only in `docs/09-roadmap.md`, `docs/10-codex-backlog.md`, `docs/22-phase-gates.md`, and the implementation plan.
5. Proposed technical defaults in these docs. Do **not** silently elevate proposals into owner-approved decisions.

When instructions conflict, explain the conflict and choose the safer, less invasive implementation; ask the owner before irreversible architecture decisions. Do not replace Next.js/TypeScript, FastAPI/Python, Supabase Postgres, Supabase Storage, OpenAI or custom email/password authentication. Develop locally now; target Docker-on-VPS later.

## 1. Project identity and scope
- Repository: `agent-hub`; product: AgentHub.
- Confirmed: **Next.js/TypeScript frontend**, FastAPI/Python backend, Supabase PostgreSQL, Supabase Storage, **OpenAI** as LLM provider, **custom email/password auth owned by FastAPI (not Supabase Auth)**; initial use case: fashion shop; initial channel: embeddable website chat widget.
- Confirmed environments: local development **now**, Docker containers deployed to VPS **later**. Do not substitute a managed app-hosting platform or require VPS access to complete foundation work.
- Long-term: multiple workspaces, agents, knowledge sources, channels; Facebook/Zalo and other business use cases follow the MVP.
- `docs/00-decisions.md` is the source of truth for confirmed vs proposed vs deferred scope.

## 2. Non-negotiable invariants
- All tenant-owned reads/writes/queries/tools/storage objects/embedding searches are scoped to a validated `workspace_id`; never trust a workspace ID from the client without checking membership or widget scope.
- Never put DB credentials, Supabase secret/service keys, LLM API keys, JWT signing keys or customer-private file URLs in browser bundles, logs or commits.
- Browser/widget -> FastAPI -> Postgres/Storage/LLM. Do not connect browser directly to privileged Supabase database or Storage operations. Our custom auth tokens **are not** automatically Supabase Auth tokens.
- Product price, SKU, size/color options and stock come from structured catalog records at answer time. Never invent availability, discount, shipping commitments or order outcomes.
- Treat documents, user prompts and customer images as untrusted data; never let retrieved content override system/tool instructions.
- Require authorization before creating Storage signed URLs or returning product/shop data. Use private buckets for customer uploads and knowledge documents.
- No autonomous payments, order placement, refunds or stock mutation in MVP.
- Handle errors without leaking prompts, keys, personal data or traceback details to users.

## 3. Working agreement
Before implementation:
1. Identify the roadmap task and explicitly list acceptance criteria.
2. Read `docs/03-architecture.md`, `docs/04-data-model.md`, `docs/05-api-contract.md`, `docs/06-agent-and-rag.md`, `docs/07-ux-flows.md`, and `docs/08-security.md` as applicable.
3. State which choices are confirmed and which are only proposed. Make the smallest coherent change.
4. Consult `docs/design/reference-assets.md` and all 3 images for UI work; written UX/accessibility rules override image inaccuracies. Foundation work delivers a styled scaffold and local health check, not authentication/catalog/RAG/widget production features. Never display mockup sample metrics or false Facebook/Zalo connection states as real.

While implementing:
- Prefer clear FastAPI boundaries: routers -> service/use-case -> repositories/providers. Pydantic contracts; SQLAlchemy + Alembic are **proposed defaults**, not owner-confirmed facts.
- Use Python type hints, focused modules, transactional DB changes, idempotent ingestion jobs, consistent error envelopes and structured redacted logs.
- Use OpenAI behind an adapter to isolate SDK/model upgrades; do **not** implement extra LLM providers without a scoped task. Tools must validate inputs and execute with independently enforced workspace scope.
- Add/modify migrations for schema changes; do not edit production DB manually.
- Use UUIDv7 for users/workspaces and exposed agent/conversation public IDs only; BIGINT identity for internal tables. Generate v7 server-side; never quietly use v4 or assume PostgreSQL native uuidv7() is installed. `workspace` is the tenant and `agent` is the domain model (shop/chatbot are UI language).
- Avoid introducing Redis, queue workers, LangGraph, billing, VPS provisioning or social-channel SDKs before a task requires them.
- Keep `.env.example` minimal: include only secret placeholders, values without a safe application default, and settings that genuinely vary by deployment. Stable limits and tuning defaults belong in typed application configuration; do not duplicate them in `.env.example`. Document optional overrides without pre-populating them.

Before claiming completion:
- Run relevant lint, type, unit, integration and migration tests if their tooling exists; report exact commands/results. Never claim tests ran when they did not. Local boot is the foundation exit gate; Docker/VPS only when the rollout work is requested.
- Cover a negative cross-workspace test for every newly exposed tenant-owned resource.
- Update docs and `.env.example` when behavior/configuration changes.
- Summarize files changed, migration/deployment impact, manual verification steps and known limitations.

## 4. Commands
Actual package manager and commands must be written in README after scaffolding. **Do not invent working commands.** Suggested defaults pending implementation: `pytest`, `ruff check .`, `mypy`, `alembic upgrade head`, `pnpm lint`, `pnpm test`, `pnpm build`.

## 5. Suggested repository shape (not yet implementation)
```
agent-hub/
  AGENTS.md
  README.md
  docs/           # numbered master docs + design/ + architecture/
  assets/reference/ # 3 mockups (UI reference, NOT production catalog photos)
  apps/
    api/          # FastAPI
    web/          # owner dashboard; Next.js + TypeScript CONFIRMED
    widget/       # embeddable website chat
    worker/       # only when async jobs outgrow in-process MVP
  packages/       # shared frontend contracts/design system if needed
  infra/        # local tooling now; Docker/VPS packaging later
```

## 6. Broader documentation and delivery scope
`docs/12-full-product-scope.md` through `docs/23-decision-and-change-control.md` describe the **target product** and later delivery phases. They do not authorize Codex to implement post-MVP features. Current implementation starts only from a named, accepted task in `docs/10-codex-backlog.md`; see `docs/22-phase-gates.md`.

## 7. Definition of done
Acceptance criteria pass; authn/authz and tenant isolation covered; user data handled safely; API schemas and UI errors documented; no secrets; migrations reversible when practical; test results stated accurately; no deferred features implemented without approval.
