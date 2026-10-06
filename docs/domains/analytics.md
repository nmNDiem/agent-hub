# Analytics

## Purpose

Analytics turns persisted operational facts into understandable measures. It must not invent business impact, cost or attribution that the system does not record.

## Current capability

- Workspace-local 7/30-day conversation and completed-reply activity.
- Active Website agents, recent conversations/leads and monthly generation quota.
- Generation/vision usage events with observed model/tool calls and token counts.
- No estimated provider cost or unsupported sales metric.

## M1 capability

- Volume and delivery outcomes by channel and agent.
- First response and human response timing from persisted timestamps.
- AI resolved, human handled and unresolved/handoff outcomes using explicit workflow states.
- Lead conversion from recorded consented lead events.
- Product interest from structured product-card/impression/click events where disclosed and implemented.
- Filters with bounded queries and workspace-local timezone definitions.

## Later capability

- Agent evaluation and feedback trends.
- Retrieval-empty, unanswered-question and regression quality measures.
- Configurable provider cost derived from versioned price data rather than hardcoded constants.

## Invariants

- Every metric has a written numerator, denominator, time boundary and timezone.
- Dashboard values come from persisted tenant-scoped data, never mockups.
- Analytics does not duplicate raw conversations, images or contact PII without a documented need.
- Unknown and unavailable data render as such; they are not converted to zero or success.
