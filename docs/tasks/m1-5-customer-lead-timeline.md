# M1.5 Customer and lead timeline

## Goal

Deliver one consent-aware contact record across Website, Facebook and Zalo with an operational
timeline, reversible duplicate resolution and bounded retention/export behavior.

## Acceptance criteria

- Workspace-scoped contacts link Website leads and connection-namespaced Facebook/Zalo identities.
- Website email/phone values are never auto-merged; matching values surface only as duplicate
  candidates, and display names never establish identity.
- Contact detail exposes conversations, lead state, notes, tags, assignee and a chronological audit
  timeline without copying message bodies or raw provider payloads.
- Owner/admin can operate every contact. Members can see unassigned or self-assigned contacts,
  claim an unassigned contact and operate only a self-assigned contact.
- Contact mutations enforce CSRF, role, tenant scope and optimistic state conflicts.
- Merge is logical, audited and reversible; it cannot create chains/cycles or destructively move
  source records.
- Owner/admin contact export is bounded, formula-safe and excludes identity hashes, raw provider
  payloads and internal audit details.
- Contact retention follows the longest current purpose-specific deadline and removes PII and
  operational metadata when the deadline expires.
- Existing Website leads are backfilled without losing consent, follow-up or retention provenance.
- Every newly exposed tenant resource has negative cross-workspace coverage.

## Confirmed decisions

- Contacts own consented identity relationships; channel external IDs remain namespaced by provider
  and connection.
- A Website lead creates a distinct contact. Equal unverified email/phone values are review signals,
  not automatic links.
- A first Facebook/Zalo thread creates its contact and provider identity in the same transaction.
- Merge uses an active source-to-target link plus an immutable event; reversal is allowed only while
  that event remains the active merge.
- Leads remain follow-up records attached to contacts rather than becoming a competing customer
  model.
- Existing 30-day Website lead and social-message defaults supply the initial contact deadline.
- No dependency, external service, Redis or workflow framework is added.

## Data/API/UI/security impact

- Add contacts, contact identities, notes, workspace tags/contact links, audit/merge events and
  contact references on conversations and leads, with a migration that backfills current leads.
- Add authenticated contact list/detail/timeline, state, note, tag, merge/reverse and CSV export APIs.
- Extend verified social inbound and Website lead capture to create purpose-scoped contacts.
- Replace the lead-only navigation with a responsive Contacts list/detail workspace and link Inbox
  threads to their contact.
- Keep PII out of logs, public APIs, provider payload storage and unauthorized member responses.

## Test plan

- Unit/API tests for contact creation, role visibility, filters, timeline, optimistic mutations,
  duplicate signals, merge/reversal constraints, export and retention.
- Negative cross-workspace and CSRF tests for each new read/write path.
- Channel/lead tests for transactionally linked contacts without paid/provider calls.
- Frontend tests for list/detail, timeline, assignment, notes/tags, merge confirmation and states.
- Alembic upgrade/downgrade rehearsal plus ruff, mypy, pytest, lint, typecheck and frontend tests.

## Documentation impact

- Update `domains/contacts.md`, `domains/channels.md`, `data-model.md`, `api.md`, `ui.md`,
  `testing.md` and roadmap status after executable behavior is complete.

## Out of scope

- Marketing consent campaigns, CRM automation, orders/payments and provider profile enrichment.
- Fuzzy or AI-based identity matching and automatic email/phone merges.
- Full transcript/provider-payload export and analytics beyond persisted timeline facts (M1.6).
