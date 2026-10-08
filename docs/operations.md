# Local operations

## Install and run

Current baseline is Node.js 24, pnpm 10.33.0 and Python 3.12.

```powershell
pnpm install --frozen-lockfile
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
pnpm db:migrate
pnpm dev
```

Individual services use `pnpm dev:api`, `pnpm dev:web`, `pnpm dev:worker`,
`pnpm dev:channel-worker` and `pnpm dev:widget` when their dependencies are configured. The
channel worker claims persisted outbound deliveries and must run anywhere Facebook outbound text
is enabled. Use only isolated development PostgreSQL/Storage/Qdrant resources; secrets remain
server-only.

## Health, logs and retention

- `/health/live` checks the process. `/health/ready` checks PostgreSQL and avoids paid providers.
- Logs contain request ID, method, route template, status and duration only—never raw URL/query, headers, bodies, messages, images, tokens, object keys or PII.
- Local retention: Website session/transcript 24 hours, unattached image 30 minutes, attached image one hour and consented lead 30 days.
- Run a bounded idempotent cleanup pass with `pnpm ops:retention`. It revokes database access before Storage deletion; failed deletion remains retryable.

PostgreSQL owns relational state, Supabase Storage owns uploaded objects and Qdrant is derived/rebuildable. Restore rehearsal uses synthetic data in an isolated non-production target.

## Facebook Messenger

Production uses Supabase Vault for Page access tokens. Enable Vault in the Supabase project,
grant the API database role only the required `vault.create_secret`, `vault.secrets` and
`vault.decrypted_secrets` access, and verify store/resolve/revoke before accepting Page tokens.
Supabase keeps the per-project root key outside database data; backup/restore and project
migration procedures must preserve that key or re-store all Page credentials.

Set server-only `FACEBOOK_APP_SECRET`, a random `FACEBOOK_WEBHOOK_VERIFY_TOKEN`, and an explicitly
reviewed `FACEBOOK_GRAPH_API_VERSION`. Configure Meta's callback at
`/api/v1/webhooks/facebook`. Connection creation validates the Page token and subscribes only the
`messages` field. The Meta app/Page setup needs `pages_manage_metadata` and `pages_messaging`, and
the token must come from an actor allowed to perform the Page messaging task. Obtain the required
Advanced Access and switch the Meta app to its reviewed production mode before serving people who
do not have an app/Page role. No live provider request belongs in automated tests; use the fake
Graph/Vault adapters and perform real Page/App verification manually in a non-production Meta app.

The channel worker resolves Page tokens only for a claimed send and never logs tokens, message
text or raw provider errors. `CHANNEL_WORKER_POLL_SECONDS` controls idle polling and defaults to
two seconds. A `FACEBOOK_DELIVERY_UNKNOWN` terminal result requires operator reconciliation;
requeueing it blindly can duplicate a reply whose Graph response was lost.

## Quality commands

Frontend/widget:

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Backend from `apps/api`:

```powershell
ruff check .
mypy
pytest
alembic upgrade head --sql
```

PostgreSQL and Qdrant integrations are explicit non-production opt-ins. Automated tests use fake model/channel providers and must not incur paid calls; the owner runs budgeted provider checks manually.
