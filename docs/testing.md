# Testing and verification

## Test layers

| Layer | Required coverage |
|---|---|
| Unit | Domain rules, serializers, state transitions, normalization, policy and retry classification |
| Integration | PostgreSQL migrations/constraints/transactions, Storage authorization, provider adapters with controlled test resources |
| Contract | OpenAPI/client drift, SSE ordering, webhook verification, normalized adapter fixtures |
| UI | Loading/empty/error/forbidden, forms, responsive/keyboard/screen-reader behavior |
| End-to-end | Real local user journey across implemented components without unapproved paid automation |

## Mandatory tenant fixture

Use at least two workspaces with similar products, knowledge and external-looking IDs. Prove that neither dashboard actors, visitors, background jobs, Qdrant queries, Storage grants nor channel connections cross the workspace boundary. Every newly exposed tenant resource gets a negative test.

## Existing regression areas

- Authentication, refresh rotation/reuse, CSRF and generic failures.
- Catalog import cell states, staging/diff, atomic idempotent MERGE, SKU/identity conflicts and same-variant option search.
- Unknown versus zero stock, effective price, product-only records and location/collection scope.
- Knowledge file limits, ingestion fencing/idempotency, Qdrant tenant/source filtering and Postgres revalidation.
- Grounded runtime budgets, prompt injection, safe fallback and validated product/source evidence.
- Website session/conversation/image ownership, SSE replay/cancel, lead consent, quota and retention.

## M1 channel and inbox gates

- Invalid/missing webhook verification cannot persist or trigger work.
- Duplicate/reordered provider events do not duplicate messages, model spend or delivery.
- Provider identities are isolated by connection/workspace.
- Revoked credentials and expired permissions stop processing safely.
- Outbound retry is idempotent and terminal failure is visible.
- Human reply/assignment/status/tag operations enforce role, CSRF and tenant scope.
- AI/human handoff transitions cannot send overlapping duplicate replies.
- Contact identity linking/merge has negative tenant and reversal tests.
- Analytics definitions match persisted fixtures and do not expose PII.

The shared-foundation suite uses fake adapters and two workspaces to cover connection-scoped
event/message identity, payload-fingerprint conflicts, reordered events, handling-mode gating,
delivery idempotency, lease fencing, exhausted leases, bounded retry and terminal acceptance.
Provider tasks add signature/challenge fixtures and provider-specific payload/media limits.

The M1.1 migration gate has an opt-in PostgreSQL rehearsal that upgrades to `20261005_0013`,
seeds a Website connection/session/conversation with inbound and outbound messages, upgrades to
`20261006_0014`, verifies all shared-channel backfills and downgrades to `20261005_0013`. The
Facebook first slice additionally covers challenge/signature failure, raw-body size, Page and
workspace isolation, duplicate/reordered text events, health and revoked-connection behavior.
The Facebook outbound gate continues the same rehearsal through `20261008_0015`, verifies legacy
delivery backfill to provider acceptance plus receipt persistence, then rolls back through `0014`
to `0013`. Mock Graph tests verify bearer-token placement, official text payloads, safe provider
error classification, missing credentials, early/duplicate receipts and cross-workspace receipt
isolation. No test sends a live provider message.

The M1.2 completion gate continues through `20261008_0016`, verifies thread-policy backfill,
response/media tables and downgrade removal, then rehearses rollback through `0015`, `0014` and
`0013`. Fake tests cover duplicate-to-single-model-run behavior, response fencing, exact opt
keywords, 24-hour enforcement, media host/redirect/MIME/byte/pixel limits, private cleanup,
same-Page credential rotation, cross-workspace denial and accessible connection UI states.

The M1.3 gate continues through `20261014_0017` and covers PKCE/state construction, callback
replay and initiating-user binding, OAuth token exchange, same-OA connection identity, Vault
secret rotation, automatic refresh, invalid Zalo signatures, inbound deduplication and negative
cross-workspace access. Provider gateways and Vault are faked; automated tests never authorize or
send through a live Zalo OA.

The M1.4 gate continues through `20261014_0018` and rehearses creation/removal of inbox read,
note, tag and audit tables plus the tenant-safe assignee reference. API/widget tests cover CSRF,
role-scoped visibility, cross-workspace denial, optimistic updates, model suppression after
takeover, idempotent Website human replies and scoped transcript synchronization. Existing fake
Facebook/Zalo delivery tests cover the shared queue; no provider is called live.

## Execution rules

- Inspect repository scripts before running commands; do not invent them.
- Automated tests use fake OpenAI/channel providers unless an opt-in integration is explicitly approved and budgeted.
- Never run chatbot tests that can incur paid calls; provide manual steps for the owner.
- Report exact commands, pass/fail/skip counts and environment assumptions.
- Migration changes require upgrade and practical downgrade/rollback verification.
