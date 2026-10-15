# M1.6 Operational analytics

## Goal

Deliver workspace-scoped operational reporting for channel and agent activity, response timing,
AI/human outcomes, consented lead conversion, product-card interest and unresolved signals using
only persisted facts.

## Acceptance criteria

- Owner/admin can view 7- or 30-day analytics in the workspace timezone and filter by channel and
  agent; members are denied and cross-workspace resources remain hidden.
- Activity reports conversations, inbound and completed outbound messages by day, channel and
  agent from normalized conversation records.
- First-response and human-response averages include an explicit measured sample count and return
  unavailable rather than zero when no qualifying pair exists.
- Resolution reports AI-only resolved, human-handled resolved and unresolved conversation cohorts;
  handoffs come from explicit workflow audit transitions.
- Lead conversion uses distinct conversations with persisted consented leads and states its
  numerator and denominator.
- Product interest reports idempotently persisted product-card impressions and never labels an
  impression as a click, sale, revenue or attribution.
- Delivery outcomes and failed-reply signals derive from normalized persisted state without
  exposing provider payloads, message bodies or contact PII.
- Queries are period-bounded, indexed by workspace/filter dimensions and avoid per-row database
  requests.
- The responsive Vietnamese analytics screen includes loading, empty, error, forbidden and
  accessible tabular alternatives for visual summaries.

## Confirmed decisions

- The reporting cohort is distinct conversations with an inbound message during the selected
  half-open workspace-local period `[start, end)`.
- AI-only resolved means a cohort conversation is currently resolved and has no recorded human
  takeover or human reply. Human-handled resolved means it is currently resolved and has either.
  Open or pending cohort conversations are unresolved.
- First response measures the first completed assistant/human outbound after a conversation's first
  inbound in the period. Human response measures a takeover audit event to the first later completed
  human message. Averages exclude missing and negative pairs and expose the included sample count.
- Lead conversion is distinct cohort conversations whose consented lead was created in the same
  period divided by the cohort size.
- Product interest is a product card persisted with a completed channel response. Only impressions
  are implemented; click tracking and business attribution are not implied.
- Website has no provider delivery receipt, so provider delivery outcomes can be unavailable rather
  than synthesized as delivered.
- No dependency, cache, external analytics service or new infrastructure is added.

## Data/API/UI/security impact

- Add minimal `analytics_events` rows for product impressions, with tenant-safe conversation,
  message, agent and product references plus an idempotency constraint and reporting indexes.
- Record product impressions in the same transaction that completes Website or social responses.
- Add an authenticated read-only analytics route with period, channel and agent filters.
- Add an owner/admin Analytics navigation entry and a dedicated responsive page; retain the compact
  Overview page.
- Return aggregate identifiers/names and counts only, never message text, contact PII, raw provider
  payloads or credentials.

## Test plan

- Backend API tests for period/timezone boundaries, formulas, filters, unavailable samples,
  impression idempotency, role denial and negative cross-workspace access.
- Frontend tests for loading, populated, empty, error and forbidden states, filter requests and
  accessible data tables.
- PostgreSQL migration upgrade/downgrade rehearsal and model constraint/index coverage.
- Run focused pytest/Vitest plus Ruff, mypy, ESLint and TypeScript checks without live providers.

## Documentation impact

- Update `domains/analytics.md`, `data-model.md`, `api.md`, `ui.md`, `testing.md` and M1.6 roadmap
  status after executable behavior is complete.

## Out of scope

- Revenue, cost, ROI, sale/order attribution, predictive scoring and invented business uplift.
- Product-card click tracking, cross-device attribution or external analytics integrations.
- Agent evaluation, feedback/regression quality analytics and configurable provider pricing (M2).
- Scheduled reports, exports, arbitrary date ranges and member analytics permissions.
