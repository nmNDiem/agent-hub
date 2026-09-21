# 22 — Delivery phase gates: full system, MVP first

This document is the release plan. It does **not** authorize implementing every phase in one Codex task. Phases F0–F5 build the **local fashion-shop MVP**. P6+ are separate approvals, with Docker-on-VPS as the confirmed *future* hosting plan.

| Phase | Deliverable | Exit evidence |
|---|---|---|
| F0 | Next.js/TS + FastAPI scaffold, env templates, local run, testing and migrations | Local services boot; health and test commands documented |
| F1 | Custom email/password + sessions, tenant-aware workspace foundation | Auth negative tests, reset/refresh, cross-tenant 403/404 coverage |
| F2 | Fashion product/variant/stock/image import | Shop catalog demo; price/stock authoritative |
| F3 | OpenAI adapter, knowledge/RAG, shop agent, typed read tools | Grounded answers; prompt injection and cost tests |
| F4 | Website widget, SSE, anonymous session, image input/product cards | End-to-end local widget demo, mobile/a11y checks |
| F5 | History, consented leads, contact handoff, operational hardening | Local pilot acceptance, quotas, data handling review |
| P6 | Multi-agent/workspace UX, invitations, exports/retention refinements | Migration & role tests; no broken existing tenants |
| P7 | Dockerized services on VPS (Supabase remains hosted), HTTPS, backups/monitoring/CI rollout | Staging smoke, restore test, rollback exercise, production approval |
| P8 | Facebook adapter and shared conversation pipeline | Vendor approval, signed webhooks, dedupe/retry and real-channel pilot |
| P9 | Zalo adapter and channel operations | Vendor approval, platform-specific policy and pilot |
| P10 | Full live inbox, agent lifecycle/templates, advanced knowledge ingestion | Team permissions, queue/SLAs and lifecycle tests |
| P11 | Billing/subscriptions and expanded commerce integrations | Signed payment webhooks, ledger reconciliation, action authorization |
| P12 | Generalized non-commerce agents, connectors and workflow tools | No catalog dependency; security and tenant regression suite |

## Gates common to all phases
A named task/PR has acceptance criteria and owner approval; tests run and are reported; migrations/API changes documented; privacy/security effects reviewed; docs and example configuration updated. Any change of confirmed stack requires an explicit new owner decision recorded in `docs/00-decisions.md`.

## Important sequencing nuance
P7 may be pulled earlier **only if the owner explicitly requests VPS deployment**. Until then local execution is the actual target; design interfaces can anticipate Docker but F0–F5 must not require it. Exact order among P8–P12 can be rescheduled based on customer priorities without changing the confirmed platform scope.
