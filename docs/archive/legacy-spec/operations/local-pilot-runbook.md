# Local pilot operations and acceptance

This runbook covers the F5 local pilot only. It is not a production deployment guide and does not authorize Docker/VPS work.

## Apply migrations and check health

Run the migration before starting the new API version:

```powershell
pnpm db:migrate
```

`GET /health` and `GET /health/live` report process liveness without dependency details. `GET /health/ready` runs `SELECT 1` against PostgreSQL and returns `503` until the database is available. Readiness does not call OpenAI, Qdrant or Storage.

Every HTTP response receives a server-generated `X-Request-ID`. Access logs contain only request ID, method, route template, status and duration. The repository's `dev:api` command disables Uvicorn's raw access logger so query strings cannot bypass this policy. Any future process manager must do the same. Do not add raw URLs, query strings, headers, request/response bodies, chat text, images, credentials, tokens or lead PII to routine logs.

## Retention sweep

Local-pilot policy:

| Data | Retention/action |
|---|---|
| Widget session and transcript | 24 hours |
| Unattached visitor image | 30 minutes |
| Attached visitor image | 1 hour |
| Consented lead | 30 days |
| Catalog image grant | Its recorded expiry |
| Widget rate window | 2 hours |
| Usage event | Retained without content; conversation link cleared on purge |

Run one bounded pass:

```powershell
pnpm ops:retention
```

The default batch size is 100 per data class. A pass first revokes expired database access, removes transcript and lead PII, and marks expired images `cleanup_pending`. It then deletes private Storage objects. Successful image cleanup removes its metadata; a failed or unconfigured Storage call increments `cleanup_attempts`, stores only `storage_delete_failed` or `storage_unconfigured`, and remains retryable on the next pass. The summary log contains counts only.

Run the command repeatedly until it reports no work and `image_cleanup_failed=0`. For the local pilot, the operator may invoke it manually after test activity and at least daily while the pilot is active. Automated scheduling, alerting and multi-instance coordination belong to the separately approved deployment phase.

If Storage cleanup keeps failing:

1. Confirm server-side Supabase URL/key/bucket configuration without printing secret values.
2. Confirm the private bucket is reachable from the API host.
3. Run the sweeper again; do not manually mark rows deleted or clear their object keys.
4. Investigate using request/time and safe error code only. Never paste object contents, tokens or PII into logs or tickets.

## Usage and cost boundary

Widget and Playground share the confirmed 1,000 generated-turn limit per workspace-local calendar month. Generation reserves a turn before any provider call. Usage records observed model/tool calls and tokens but does not estimate money: exact production model IDs, provider pricing, currency and pricing-effective dates are still deployment decisions. Review the current provider price sheet and approve a production budget before P7; do not infer historical cost from the dashboard.

## Backup and restore boundary

PostgreSQL is authoritative for tenant, catalog, conversation state, usage and knowledge metadata. Supabase Storage is authoritative for private uploaded objects. Qdrant is a derived index and must be rebuilt from active PostgreSQL knowledge generations when a compatible vector backup is unavailable.

Before production, P7 must select backup locations, encryption/access controls, frequency, retention, recovery objectives and deletion propagation. A VPS snapshot would not cover external Supabase or Qdrant resources. The local pilot requires a development-only backup/restore rehearsal with synthetic data:

1. Back up the development PostgreSQL database and private Storage using the selected Supabase-supported mechanism.
2. Restore into an isolated non-production target, never over the active project.
3. Verify tenant counts, a synthetic catalog record and a private synthetic object.
4. Rebuild Qdrant from restored active generations or verify the selected compatible vector restore.
5. Run readiness and offline regression tests, then delete the isolated restore under the provider's supported process.

No restore drill is claimed until the owner records evidence below.

## Owner local-pilot and privacy/security checklist

Record date, environment/resource names without secrets, tester and evidence location. Do not place real shopper PII in this file.

- [ ] Migration head is `20261005_0013` before the API starts.
- [ ] `/health/live` returns `200`; `/health/ready` returns `200` with DB available and `503` when DB is unavailable.
- [ ] Owner can complete signup/workspace/catalog/knowledge/publish/widget text flow locally.
- [ ] Owner tests the configured provider Playground/widget flow manually; no automated paid-service test is used.
- [ ] Widget image flow uses only consented synthetic imagery and private Storage.
- [ ] Optional lead flow displays the approved consent wording and dashboard/CSV access is owner/admin-only.
- [ ] Shared monthly quota evidence is reviewed for Widget and Playground.
- [ ] An expired synthetic session/transcript/image/grant/lead/rate window is revoked and swept; a live record in another workspace remains intact.
- [ ] A simulated Storage deletion failure remains `cleanup_pending` and a later pass succeeds.
- [ ] Sample logs contain no chat text, image data, email, phone, authorization/cookie values, private object keys or raw query strings.
- [ ] Development PostgreSQL/Storage restore rehearsal and Qdrant rebuild/restore evidence are recorded.
- [ ] Allowed origins, contact destination, upload limits, local retention and model configuration are reviewed.
- [ ] Production jurisdiction/privacy notice, processor disclosures, retention periods, provider pricing/budget, backup policy, domain/TLS and secrets management remain explicitly blocked until P7 decisions are approved.

F5 closes only after this checklist is completed alongside the F5.1/F5.2 evidence. Production readiness and VPS deployment are not implied.

## Implementation verification record — 2026-10-05

- `python -m pytest apps/api/tests -m "not postgres and not qdrant"`: `89 passed, 6 deselected, 1 warning`.
- `RUN_POSTGRES_INTEGRATION_TESTS=true python -m pytest apps/api/tests/test_catalog_postgres.py -m postgres`: `5 passed, 8 warnings`; the isolated `agenthub_test` migration round-trip passed and the schema was removed afterward.
- `python -m ruff check apps/api/src apps/api/tests`: passed.
- `python -m mypy apps/api/src apps/api/tests`: passed for 134 source files.
- `python -m alembic -c apps/api/alembic.ini heads`: `20261005_0013 (head)`.
- Offline `alembic upgrade head --sql` and `alembic downgrade 20261005_0013:20261004_0012 --sql`: passed.
- The Qdrant integration test was not run because this slice does not change vector retrieval. No frontend command was run because F5.3 changes no frontend code or UI. No paid AI/provider request was made.
- `pnpm ops:retention` was not run against configured development data during automated verification; destructive behavior is covered with isolated fake-Storage/database fixtures. The owner runs it after reviewing the target environment and applying the migration.
