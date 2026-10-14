# M1.4 Unified inbox and human handoff

## Goal

Deliver one operational inbox for Website, Facebook and Zalo conversations with explicit,
auditable AI/human ownership and safe human replies.

## Acceptance criteria

- Inbox list/detail supports channel, agent, assignee, workflow status, tag and period filters.
- Unread state is tracked per workspace member and opening a thread marks it read.
- Owner/admin can operate every thread and assign any current workspace member.
- Members can see unassigned or self-assigned threads, claim unassigned threads and operate only
  self-assigned threads.
- Assignment, `open | pending | resolved`, notes and tags are tenant-scoped and audited.
- Takeover prevents queued or completing AI work from creating an overlapping reply; resume affects
  future inbound messages only.
- Human replies persist before delivery, are idempotent and expose safe delivery/retry state.
- Facebook and Zalo replies reuse the shared delivery queue and provider policy checks.
- Website inbound messages do not invoke AI in human mode and the scoped visitor can receive human
  replies without gaining access to another conversation.
- Unsafe mutations require CSRF and every new tenant-owned resource has negative cross-workspace
  coverage.

## Confirmed decisions

- Reuse the normalized conversation and outbound-delivery foundations from M1.1-M1.3.
- Preserve `router/adapter -> service -> repository/provider` boundaries.
- Owner/admin have full inbox access. Members see unassigned or self-assigned threads, may claim an
  unassigned thread and may mutate/reply only after assignment to themselves.
- Resume does not process historical backlog automatically.
- Existing membership is selectable; invitations and membership administration remain M3 scope.
- No Redis, workflow framework, new provider or dependency is introduced.

## Data/API/UI/security impact

- Add conversation assignment/version metadata plus member read state, notes, tags and audit events.
- Extend authenticated conversation APIs with filtered reads and CSRF-protected workflow mutations.
- Extend public Website conversation synchronization using the existing scoped visitor session.
- Replace the read-only conversation screen with a responsive unified inbox and reply composer.
- All reads/writes use authenticated membership or the validated Website session and server-resolved
  workspace/conversation scope.

## Test plan

- Backend tests for filters, unread/read, role matrix, assignment, workflow transitions, notes,
  tags, reply idempotency, provider windows, delivery visibility and AI/human races.
- Negative cross-workspace and CSRF tests for every new mutation/resource.
- Widget tests for human-mode inbound behavior and scoped outbound synchronization.
- Frontend tests for inbox rendering, mutations, composer state and forbidden/error states.
- Alembic upgrade/downgrade rehearsal plus lint, mypy, unit tests, TypeScript and frontend tests.

## Documentation impact

- Update `domains/conversations.md`, `data-model.md`, `api.md`, `ui.md` and `testing.md` once the
  executable behavior is complete.

## Out of scope

- Contact profiles, identity linking/merge, contact retention/export (M1.5).
- Operational analytics and SLA reporting (M1.6).
- Invitations and membership administration (M3).
- Attachments in human replies, proactive/provider marketing messages and automatic replay of
  ambiguous delivery outcomes.
