# Analytics and usage

## Function and ownership

Analytics derives understandable measures from persisted operational facts. Usage records provider/model consumption and quota facts. Neither may manufacture cost, revenue, attribution, or outcomes.

## CURRENT

- Workspace-local 7/30-day conversation activity, completed replies, active Website agents, leads, and monthly generation quota.
- Generation/vision usage with observed provider/model/token/tool-count facts.
- Channel/agent filters, response-time measures with sample counts, AI/human outcomes, lead conversion, product-card impressions, and provider delivery/failure signals.
- Product interest means an idempotently persisted impression only; Website provider-delivery status is unavailable, not synthesized.

Main data: usage events/months, narrowly allowlisted analytics events, plus bounded queries over conversations/messages/leads/deliveries. Main surface: owner/admin Analytics.

## Core flow

Persist idempotent operational/usage facts → query a tenant-scoped, timezone-bounded cohort → calculate a documented measure → return value plus sample/availability metadata → render the same definition in UI and accessible tables.

## Metric contract

Every metric states numerator, denominator, workspace timezone, half-open time boundary, cohort, and unavailable behavior. Current 7/30-day cohorts are distinct conversations with inbound activity from the first workspace-local midnight through request time. Missing response pairs are excluded and expose sample count. Empty denominators return unavailable, never fabricated zero-percent success.

## Invariants

- Tenant scope is server-derived and mandatory.
- Raw chat, images, prompts, contact PII, and provider payloads are not copied into analytics.
- Facts are idempotent and definitions are versioned when semantics change.
- No click, order, sale, revenue, cost, or uplift is inferred from an impression or lead.

## APPROVED DIRECTION

Agent evaluation, unresolved-question, retrieval-empty, feedback, and regression measures. Provider cost appears only from versioned price data and explicit calculation policy.

## NOT IMPLEMENTED

No sales attribution, revenue dashboard, estimated ROI, generic event warehouse, or current pricing oracle exists.

## Change trigger

Before adding a metric, write its decision purpose and complete definition, then prove the required source fact already exists or deliberately add the smallest privacy-safe event.

## Dependencies and conditional references

- Metrics consume facts owned by their source domains; they do not take ownership of those records.
- Load [`../data-model.md#analytics-and-usage`](../data-model.md#analytics-and-usage) for event persistence, [`../ui.md`](../ui.md) for presentation changes, and [`../testing.md`](../testing.md) when definitions/fixtures change.

## Relevant code paths

- `apps/api/src/agent_hub_api/analytics/`
- `apps/api/src/agent_hub_api/telemetry/`
- `apps/web/src/features/analytics/`
