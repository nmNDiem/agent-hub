# 09 — Delivery roadmap

Each phase should end in a runnable, reviewed increment. Architecture may anticipate broader scope; implementation stays focused on pilot usability.

| Phase | Deliverable | Exit gate |
|---|---|---|
| F0 Foundation | Repo/API/dashboard/widget skeleton, config, lint/tests, CI, migration harness | Local dev boots; test runner works; no secrets committed |
| F1 Identity & tenants | Email/password auth, verification/reset, workspace/membership, access boundaries | Auth and cross-tenant tests pass |
| F2 Fashion catalog | Product/variant/size/image CRUD, legacy CSV import, storage | Catalog demo with verified prices/stock |
| F2.1 Universal catalog import | Generic options/attributes/external refs, CSV/XLS/XLSX staging/diff/MERGE, structured search | Complete; critical PostgreSQL migration/JSONB/constraint/tenant checks passed in isolated `agenthub_test` schema |
| F2.2 Location catalog scope | Workspace master catalog, locations, location+variant inventory/pricing, collections and location-aware import/search | Complete; migration and tenant regressions preserve `NULL != 0`, and PostgreSQL stock backfill passed |
| F3 Knowledge & agent | Shop profile, FAQ, PDF/TXT ingestion, Qdrant, provider-neutral embedding adapter, agent config, typed tools over F2.1 search | Agent answers grounded questions with authoritative effective price/inventory and same-variant options |
| F4 Widget & vision | Embed, visitor sessions, SSE, schema-neutral product cards, visitor photo flow | Complete locally; isolated real-page embed passed desktop/mobile/a11y and cross-session/card/image regressions |
| F5 Local operational pilot | Leads, callback, dashboard history/usage, limits, local observability | Owner tests end-to-end locally; privacy/security review completed |
| P6+ Full product & future deployment | Role invitations, multi-agent, Docker-on-VPS, channel adapters, knowledge expansion, billing | Explicit new phase approvals; see `22-phase-gates.md` |

Full target scope is specified in `12-full-product-scope.md` through `23-decision-and-change-control.md`. These do not authorize implementation beyond the current task.

## Dependencies
F1 precedes private F2/F3 endpoints; F2.1 precedes F2.2; F2.2 location/collection-scoped search precedes F3 agent assignments and typed catalog tools. F3 is delivered through the ordered F3.1–F3.5 implementation slices defined in `10-codex-backlog.md`, but remains one roadmap phase and exit gate. F3 precedes grounded F4 widget answers and product cards; F4 precedes pilot; F5 confirms usability and operations.

## Not now
Checkout/payment/order writes; drag-drop workflow editor; subscriptions; live staffed inbox; Facebook/Zalo; periodic website scraping; automatic inventory integrations. Add only under a separate approved scope and threat review.
