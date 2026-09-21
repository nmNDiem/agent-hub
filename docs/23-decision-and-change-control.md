# 23 — Open decisions, ADRs and controlled change

## Immutable until owner changes them
Repo/product `agent-hub`/AgentHub; Next.js + TypeScript frontend; FastAPI/Python backend; Supabase PostgreSQL + Supabase Storage; custom FastAPI-managed email/password authentication (not Supabase Auth); OpenAI provider; fashion-shop first MVP; website first channel; run **locally now**, Docker on **VPS later**. Do not reclassify any of these as PROPOSED.

**Latest owner ID decision (2026-09-21):** UUIDv7 selectively, BIGINT IDENTITY internally; see `architecture/identifiers.md`. Technical naming convention `workspace`/`agent` prevents duplicate shop/bot persistence and API surfaces.

## Decisions that remain open
- UI styling library (Tailwind/shadcn proposed in design handoff, not yet an explicit owner stack decision); ORM/DB driver/migration tooling; widget build packaging; optional queue, redis, orchestration framework.
- Exact OpenAI chat/vision/embedding model IDs, version/pinning, budgets, eval fixtures and retry parameters.
- Email delivery and verification mechanisms, password/session lifetimes and key rotation schedule.
- Dev Supabase setup (separate hosted dev project vs local compatible stack), package manager and final developer commands.
- Customer data retention windows, allowed file/domain policies, local pilot limits, pricing and customer agreements.
- Eventual VPS vendor/resources, domain/TLS/reverse proxy, operational staffing and off-site backup destination.

## Architectural decision record template
```
# ADR-NNN: <question>
Status: proposed | accepted | superseded
Context:
Options and trade-offs:
Decision and owner approval reference:
Consequences and reversibility:
Affected docs, tests and migration plan:
```

## Codex change protocol
1. Identify the current phase/task and read relevant docs.
2. Preserve confirmed decisions; propose only the smallest needed open choice.
3. If a requirement conflicts with a confirmed choice, call it out rather than changing implementation silently.
4. Avoid implementing P6+ while assigned F0–F5, even when the target architecture documents it.
5. On owner approval, update decision register and dependent documents in the **same change** to prevent stale guidance.

## Status discipline
These documents describe design intent, not implementation evidence. No file may claim working app, successful tests, VPS deployment, production readiness or compliance absent actual verification.
