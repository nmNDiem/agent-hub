# Contacts and leads

## Purpose

Contacts represent consented customer identity and relationship history across channels. A lead is a business follow-up state, not a replacement for the contact model.

## Current capability

- Website callback consent creates a distinct contact with normalized email/phone identity,
  consent version/time and server-derived lead/conversation ownership. Anonymous visitors remain
  usable without providing identity.
- First verified Facebook or Zalo inbound activity creates a distinct provider-asserted identity
  namespaced by workspace connection; display names and unverified provider data never join contacts.
- The workspace contact list supports stable cursor pagination, display-name/email/phone search,
  shared tags and assignment filters. Owner/admin can operate all contacts; members can see
  unassigned or self-assigned contacts and claim an unassigned contact.
- Contact detail aggregates identities, conversations, leads, notes, state history and merge
  history. A lead keeps its independent `new | contacted | closed` follow-up state.
- Exact normalized email/phone matches are suggestions only. Owner/admin must supply a reason to
  perform a version-checked logical merge; source data remains in place and the merge is auditable
  and reversible. Merge chains and cycles are rejected.
- Owner/admin can download a bounded, formula-safe CSV that excludes channel external IDs, raw
  provider data and internal audit details.
- Contact and identity deadlines inherit their source conversation/lead retention. Expiry removes
  identities, notes, tags, assignment, display name and merge reasons while retaining content-free
  audit facts.

## Invariants

- Never infer that two people are the same from display name alone.
- Email/phone or channel identity is linked only under documented verification/consent rules.
- Client-supplied workspace, agent or conversation ownership is never trusted.
- Contact PII is restricted by role, excluded from routine logs and not echoed from public creation APIs.
- Identity linking and merges require audit evidence and a recovery strategy.
- Retention applies by data purpose; channel-provider retention is not assumed to match AgentHub policy.
