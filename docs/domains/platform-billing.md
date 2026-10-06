# Platform and billing

## Purpose

The platform domain manages commercial entitlements, usage limits and operator controls across workspaces. It is a committed later delivery after omnichannel operations and product intelligence.

## Current foundation

- Tenant-scoped factual usage events.
- A transactional local generated-turn quota shared by Website and Playground.
- Rate, upload, token, tool and provider-call safety limits.
- No subscriptions, invoices or customer charging.

## Complete domain capability

- Plans and versioned entitlements.
- Workspace subscription lifecycle and commercial quotas.
- Immutable metering/credit ledger where financial correctness requires it.
- Invoices, signed payment webhooks, replay-safe reconciliation and refunds/disputes policy.
- Platform operator controls with audited, least-privilege support access.
- Trial, active, restricted, suspended, export and deletion states.

## Invariants

- Provider usage and customer billing are separate facts.
- Prices and entitlement rules are versioned; they are not assumed from current provider pricing.
- Webhooks are signature-verified and idempotent.
- Card data is not handled directly when a payment provider can host collection.
- Model output cannot change plans, charge customers or grant entitlements.
- Suspension stops new paid work according to policy while preserving lawful account/export access.
