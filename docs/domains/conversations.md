# Conversations

## Purpose

Conversations are normalized customer threads across Website, Facebook and Zalo. They retain channel provenance while presenting one operating model for AI and human participants.

## Current capability

- Website visitor session and one scoped conversation.
- Idempotent persisted messages with SSE generation/replay.
- Safe product/source evidence and visitor-image metadata.
- Owner/admin read-only history with stable cursor pagination.
- Retention and deletion behavior for local-pilot visitor data.

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
- Message DTOs omit private object paths, credentials and raw provider payloads.
- Handoff does not falsely claim that a human is available.

The M1 UI is described in [`../design/screens/inbox-contacts.md`](../design/screens/inbox-contacts.md).
