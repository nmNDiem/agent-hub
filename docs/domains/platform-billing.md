# Platform billing and entitlements

## Function and ownership

This domain will sell AgentHub itself: plans, workspace entitlements, quotas, subscriptions, and operator account controls. It is distinct from Commerce payments a workspace may collect from its customers.

## CURRENT

- Tenant-scoped factual usage events.
- A transactional generated-turn quota shared by Website and Playground.
- Rate, upload, token, tool, provider-call, and concurrency safety limits.
- No subscription, invoice, card collection, or customer charging.

Main data today: usage events and workspace usage months. Main surfaces today: usage/quota visibility; there is no billing console.

## Core flow

Reserve a generated turn transactionally against the workspace-local month → perform bounded provider work → persist observed usage outcome. This is safety/quota enforcement, not commercial invoicing.

## Invariants

- Provider consumption and customer billing are separate facts.
- Entitlements are checked server-side, not inferred from UI visibility.
- Prices and plan rules are versioned; current provider prices are never hardcoded as timeless truth.
- Prefer hosted payment collection and retain no card data when a provider can own it.
- Signed webhooks are verified and idempotent before state change.
- Model output cannot change plans, charge customers, or grant entitlements.

## APPROVED DIRECTION

Plans, versioned entitlements, workspace subscription lifecycle, commercial quotas, invoices, replay-safe webhook reconciliation, refund/dispute policy, and narrowly authorized operator controls. Financial correctness may require an immutable metering/credit ledger.

## NOT IMPLEMENTED

All commercial billing behavior above is absent. There is no general platform audit table or support impersonation flow.

## Change trigger

Before charging the first workspace, select the external provider and document price versioning, entitlement transitions, webhook/reconciliation behavior, failure states, support access, export, suspension, and deletion.

Related authority: [`../roadmap.md`](../roadmap.md), [`../security.md`](../security.md), [`commerce.md`](commerce.md).
