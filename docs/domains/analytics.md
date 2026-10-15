# Analytics

## Purpose

Analytics turns persisted operational facts into understandable measures. It must not invent business impact, cost or attribution that the system does not record.

## Current capability

- Workspace-local 7/30-day conversation and completed-reply activity.
- Active Website agents, recent conversations/leads and monthly generation quota.
- Generation/vision usage events with observed model/tool calls and token counts.
- Owner/admin operational analytics with channel and agent filters.
- First-response and human-response averages with measured sample counts.
- AI-only resolved, human-handled resolved, unresolved and handoff measures.
- Consented lead conversion and product-card impressions from persisted facts.
- Provider delivery outcomes and failed-reply signals without exposing payloads or PII.
- No estimated provider cost or unsupported sales metric.

## Metric definitions

- Reports use a half-open 7- or 30-day period from the first workspace-local midnight through the
  request time. The cohort is distinct active conversations with an inbound message in that period.
- First response is the first completed assistant/human outbound after the cohort conversation's
  first inbound in the period. Human response is a recorded transition to human mode followed by
  the first completed human reply. Missing pairs are excluded and reported with a sample count.
- AI-only resolved is a currently resolved cohort conversation with no human takeover or human
  reply. Human-handled resolved has either fact. Open/pending cohort conversations are unresolved.
- Lead conversion is distinct cohort conversations with a consented lead created in the same
  period divided by the cohort size. An empty denominator produces unavailable, not zero percent.
- Product interest is an idempotently persisted product-card impression. No product click, order,
  sale, revenue or attribution is inferred.
- Website responses have no provider receipt, so provider delivery outcomes are unavailable for
  Website rather than synthesized as delivered.

## Later capability

- Agent evaluation and feedback trends.
- Retrieval-empty, unanswered-question and regression quality measures.
- Configurable provider cost derived from versioned price data rather than hardcoded constants.

## Invariants

- Every metric has a written numerator, denominator, time boundary and timezone.
- Dashboard values come from persisted tenant-scoped data, never mockups.
- Analytics does not duplicate raw conversations, images or contact PII without a documented need.
- Unknown and unavailable data render as such; they are not converted to zero or success.
