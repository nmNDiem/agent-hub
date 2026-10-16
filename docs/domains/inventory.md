# Inventory

## Function and ownership

Inventory owns stock truth for Commerce. Catalog identifies the product variant and location; Inventory explains availability and, once operational writes exist, why balances changed.

## CURRENT

`inventory_levels` stores a mutable current quantity per workspace/location/variant. `NULL` means unknown; zero means known out of stock. Catalog CRUD/import and read-only agent search can expose this bounded fact.

There is no stock movement history, reservation, allocation, receipt, adjustment reason, transfer, sale deduction, return receipt, or reconciliation workflow. The current quantity is therefore a presentation fact, not a sufficient operational ledger.

## Core flow

An authorized catalog operation sets/imports current quantity → PostgreSQL persists it → catalog search resolves the effective scoped record → an Agent may read it → UI renders validated availability. No model output may mutate it.

## Invariants

- Workspace/location/variant ownership is checked together.
- Unknown is distinct from zero and must remain distinct in APIs and UI.
- Availability claims use current authoritative PostgreSQL state, not Qdrant, prompt context, or cached model text.
- Concurrent operational writes cannot be introduced on top of unexplained last-write-wins quantity.

## APPROVED DIRECTION

Before the first operational stock mutation, add an append-only movement ledger and derive/reconcile current balances transactionally. The task must define:

- movement types and immutable source references;
- positive/negative sign convention and unit precision;
- idempotency and duplicate-source constraints;
- concurrency/locking strategy and negative-stock policy;
- reservation versus on-hand versus available semantics, if required;
- adjustment authorization and reason evidence;
- backfill/migration from current quantities;
- reversal/correction rather than destructive editing;
- audit, retention, reporting, and failure behavior.

## NOT IMPLEMENTED

The ledger and every operational movement listed above are absent. Do not describe current quantities as event-sourced, auditable stock history.

## Change trigger

An order reservation, sale, return, receiving, transfer, adjustment, purchasing, or POS workflow is blocked on the approved ledger design and migration. The ledger should not be built earlier merely as generic infrastructure.

## Dependencies and conditional references

- Variant/location identity belongs to [`catalog.md`](catalog.md); transactional sequencing belongs to [`commerce.md`](commerce.md).
- Load [`../data-model.md#catalog-and-current-inventory-view`](../data-model.md#catalog-and-current-inventory-view) for current persistence or any approved ledger schema work.

## Relevant code paths

- `apps/api/src/agent_hub_api/catalog/`
- `apps/web/src/features/catalog/`

There is no separate Inventory service/module today; creating one is justified only by the operational-mutation trigger above.
