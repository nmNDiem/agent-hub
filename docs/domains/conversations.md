# Conversations

## Purpose

Conversations are normalized customer threads across Website, Facebook and Zalo. They retain channel provenance while presenting one operating model for AI and human participants.

## Current capability

- Website visitor session and one scoped conversation.
- Idempotent persisted messages with SSE generation/replay.
- Safe product/source evidence and visitor-image metadata.
- Owner/admin read-only history with stable cursor pagination.
- Retention and deletion behavior for local-pilot visitor data.
- Channel-neutral conversation/message ownership with explicit inbound/outbound direction.
- A connection-scoped external thread/message identity model for social adapters.
- Independent `active | deleted` lifecycle, `open | pending | resolved` workflow status and
  `ai | human | paused` handling mode; existing Website conversations default to
  `active/open/ai`.
- Persisted outbound delivery state with lease fencing and bounded retry.
- Facebook response jobs with independent lease fencing, one job per inbound message and explicit
  completed/retryable/terminal/suppressed outcomes.

## Complete domain capability

- Unified multi-channel inbox.
- Explicit `ai`, `human` or `paused` handling mode.
- Human reply composer and provider delivery status.
- Unread/read state, assignment, open/pending/resolved status, notes and tags.
- Safe retry and failure visibility without duplicate outbound messages.
- Handoff from AI to a person and controlled resume of automation.
- Filters by channel, agent, assignee, status, tag and period.

## Invariants

- A provider retry cannot create a second message, conversation or paid model turn.
- Persist inbound messages before processing and outbound attempts before provider delivery.
- Public/widget sessions cannot read another session's thread.
- AI/human authorship and delivery state are explicit and auditable.
- Only `ai` mode may schedule automated generation; duplicate inbound work never schedules it.
- Provider opt-out and response-window policy is rechecked before generation completion and send.
- Message DTOs omit private object paths, credentials and raw provider payloads.
- Handoff does not falsely claim that a human is available.

The M1 UI is described in [`../ui.md`](../ui.md).
