# Conversations

## Function and ownership

Conversations normalize Website, Facebook, and Zalo threads into one AI/human operating model while retaining channel provenance and delivery truth.

## CURRENT

- Scoped Website sessions and persisted streaming/replay.
- Conversation lifecycle, `open | pending | resolved` workflow, and `ai | human | paused` handling mode.
- Idempotent messages, external thread/message mappings, response jobs, and outbound deliveries.
- Unified Inbox with filters, per-member unread state, assignment, notes, tags, takeover/resume, human replies, and provider delivery state.
- Role-aware access: owner/admin see the workspace; members see unassigned or self-assigned threads and may claim unassigned work.
- Safe product/source evidence is stored in message response JSON; there is no separate message-evidence table.

Main data: conversations/messages, read states, notes/tags, conversation audit events, channel mappings/jobs/deliveries, and Website sessions. Main surface: Inbox and scoped visitor transcript.

## Core flow

Persist and deduplicate inbound message → evaluate explicit handling state/provider policy → schedule at most one response job → persist assistant/human outbound message before delivery → deliver or stream → retain exact outcome → update read/workflow state through authorized operations.

## Invariants

- Public/widget sessions cannot read another session's thread.
- Only `ai` mode schedules new automated responses; takeover fences both job claim and completion.
- Resume affects future inbound messages, not historical backlog.
- AI/human authorship, direction, processing, and provider delivery are explicit.
- Handoff never claims a human is available unless the product actually knows that.
- Retention removes sensitive content without inventing delivery or audit facts.

## APPROVED DIRECTION

Quality/evaluation links may reference conversations without duplicating their sensitive content. Future domain actions may be presented in a conversation only after their owning service authorizes and records them.

## NOT IMPLEMENTED

No general `agent_tool_calls` table, universal workflow state machine, staffed-SLA scheduler, or cross-workspace shared inbox exists.

## Change trigger

Any new participant, delivery class, or action card must define authorship, authorization, idempotency, retention, fallback, and accessible rendering.

Related authority: [`channels.md`](channels.md), [`contacts.md`](contacts.md), [`../ui.md`](../ui.md).
