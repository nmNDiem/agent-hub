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
- M1.4 adds one Website/Facebook/Zalo inbox with channel, agent, assignee, workflow, tag and period
  filters; per-member unread state; assignment; internal notes and normalized tags; and visible
  provider delivery state.
- Owner/admin can operate every workspace thread. Members can see unassigned and self-assigned
  threads, claim an unassigned thread and operate only a self-assigned thread.
- Takeover moves a thread to `human` and suppresses AI output at claim and completion fences.
  Resume affects future inbound messages only.
- Human replies persist idempotently before delivery. Facebook/Zalo reuse the durable queue and
  response-window enforcement; Website replies remain scoped to the originating visitor session.
  The Website transcript exposes only a handoff-waiting flag so the widget can restore scoped
  polling while its panel is open after reload, and stop it when the panel closes or AI handling
  resumes.

## Complete domain capability

The M1.4 operational inbox capabilities above are implemented. Every Website lead and verified
social thread now links to a workspace-scoped contact, and authenticated inbox summaries expose
the safe contact public ID for contact-timeline navigation. Analytics derived from these persisted
facts remains in M1.6.

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
