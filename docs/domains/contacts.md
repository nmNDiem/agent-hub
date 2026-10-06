# Contacts and leads

## Purpose

Contacts represent consented customer identity and relationship history across channels. A lead is a business follow-up state, not a replacement for the contact model.

## Current capability

- Optional Website callback form with versioned explicit consent.
- Validated email or phone, server-derived workspace/session/conversation scope and idempotent creation.
- Owner/admin lead list, `new | contacted | closed` state and formula-safe CSV export.
- Anonymous Website visitors remain usable without providing identity.

## Complete domain capability

- Workspace-scoped contact profile and interaction timeline.
- Multiple namespaced channel identities linked to a contact.
- Leads, notes, tags, assignee and follow-up state.
- Safe contact search, duplicate review and reversible merge/link operations.
- Consent purpose/version evidence, export and erasure workflow.

## Invariants

- Never infer that two people are the same from display name alone.
- Email/phone or channel identity is linked only under documented verification/consent rules.
- Client-supplied workspace, agent or conversation ownership is never trusted.
- Contact PII is restricted by role, excluded from routine logs and not echoed from public creation APIs.
- Identity linking and merges require audit evidence and a recovery strategy.
- Retention applies by data purpose; channel-provider retention is not assumed to match AgentHub policy.
