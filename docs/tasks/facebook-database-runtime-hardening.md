# Facebook database runtime hardening

## Goal

Complete the Facebook rollout safely by detecting schema drift, bounding application database
pool usage, and removing avoidable channel-worker database pressure before upgrading the approved
Supabase database from revision `20261005_0013` to `20261008_0016`.

## Acceptance criteria

- Readiness returns `503` unless PostgreSQL is reachable and Alembic is at the application schema
  revision, without exposing revision details publicly.
- API and worker engines use explicit typed pool, overflow, checkout and connect-timeout limits.
- Failed Facebook media cleanup yields to the configured worker poll interval.
- Facebook connection summaries fetch only the latest response job and delivery per connection.
- Existing Facebook fake-provider tests and focused database/configuration tests pass.
- The approved database upgrades from `20261005_0013` to `20261008_0016` and readiness succeeds.

## Confirmed decisions

- Keep SQLAlchemy async with asyncpg and the current Supabase Session Pooler connection.
- Do not switch runtime traffic to Transaction Pooler solely because the Facebook rollout exposed
  new TLS handshakes.
- Use the existing Alembic chain; do not edit generated or applied migration history.
- Do not call live Meta or paid model APIs during automated verification.

## Data/API/UI/security impact

- Data: apply existing channel migrations `0014` through `0016`; no new migration is introduced.
- API: `/health/ready` additionally validates the application schema revision; response shape stays
  unchanged.
- UI: no behavior or layout change.
- Security: readiness and logs expose no database URL, credentials, or actual/expected revisions.

## Test plan

- Unit-test pool configuration and validation.
- Unit-test readiness for matching and mismatched revisions.
- Test Facebook cleanup failure behavior and bounded latest-state summaries.
- Run focused Ruff, mypy and pytest checks for changed modules.
- Run the documented Alembic upgrade and verify revision plus `/health/ready`.

## Documentation impact

- Update operations guidance to state that readiness includes schema compatibility and document
  the bounded database pool defaults.

## Out of scope

- Switching database drivers or Supabase connection mode.
- Changing Facebook provider behavior, UI, message policy or live credentials.
- Adding migrations beyond the existing `0014`-`0016` chain.
