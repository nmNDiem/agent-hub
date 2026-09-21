# ADR-0001 — Foundational stack, IDs, tenant and publish boundaries

Status: Accepted for this handoff (2026-09-21).

**Context.** Need a locally runnable shop chatbot with long-lived path to channel integrations and VPS, while keeping a fast UI and avoiding UUID proliferation.

**Decision.** Next.js/TS + FastAPI + Supabase PostgreSQL/Storage + OpenAI; tenant-scoped domain; trusted server-only secrets; primary `BIGINT IDENTITY` for high-volume/internal rows; UUIDv7 public IDs and stable globally exposed actors; custom secure email/password; draft/published bot revisions; Web first. For UUIDv7 portability backend generation is canonical, SQL column type `uuid`.

**Consequences.** Extra unique public IDs for a few internal BIGINT tables are intentional; API never trusts row IDs without checking shop membership. Additional auth/security work belongs to our backend. Later channels must route through core chat and obey the same shop/bot permission checks.

**Not decided by prior conversation.** A forced two-repository split; this handoff supports both. If split, use OpenAPI CI and versioned docs to prevent contract drift.
