# 09 — Delivery roadmap

Each phase should end in a runnable, reviewed increment. Architecture may anticipate broader scope; implementation stays focused on pilot usability.

| Phase | Deliverable | Exit gate |
|---|---|---|
| F0 Foundation | Repo/API/dashboard/widget skeleton, config, lint/tests, CI, migration harness | Local dev boots; test runner works; no secrets committed |
| F1 Identity & tenants | Email/password auth, verification/reset, workspace/membership, access boundaries | Auth and cross-tenant tests pass |
| F2 Fashion catalog | Product/variant/size/image CRUD, CSV import, storage | Catalog demo with verified prices/stock |
| F3 Knowledge & agent | Shop profile, FAQ, PDF/TXT ingestion, pgvector, agent config, typed tools | Agent answers grounded questions with accurate catalog data |
| F4 Widget & vision | Embed, visitor sessions, SSE, product cards, visitor photo flow | Real shop test page can use chat anonymously |
| F5 Local operational pilot | Leads, callback, dashboard history/usage, limits, local observability | Owner tests end-to-end locally; privacy/security review completed |
| P6+ Full product & future deployment | Role invitations, multi-agent, Docker-on-VPS, channel adapters, knowledge expansion, billing | Explicit new phase approvals; see `22-phase-gates.md` |

Full target scope is specified in `12-full-product-scope.md` through `23-decision-and-change-control.md`. These do not authorize implementation beyond the current task.

## Dependencies
F1 precedes private F2/F3 endpoints; F2 precedes trustworthy product recommendations; F3 precedes grounded widget answers; F4 precedes pilot; F5 confirms usability and operations.

## Not now
Checkout/payment/order writes; drag-drop workflow editor; subscriptions; live staffed inbox; Facebook/Zalo; periodic website scraping; automatic inventory integrations. Add only under a separate approved scope and threat review.
