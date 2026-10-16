# Local operations

Load the relevant section only for setup, deployment/provider configuration, retention jobs, health, backup or recovery work. Routine feature implementation should not preload this file.

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
channel worker claims persisted Facebook/Zalo response jobs, performs bounded private-media cleanup
and sends outbound deliveries; it must run anywhere channel automation is enabled. Use only
isolated development PostgreSQL/Storage/Qdrant resources; secrets remain server-only.

## Health, logs and retention

- `/health/live` checks the process. `/health/ready` checks PostgreSQL connectivity and requires
  the Alembic revision expected by the running application; it avoids paid providers and returns
  only a safe unavailable state when the schema is stale.
- Each API or worker process lazily maintains at most five PostgreSQL connections by default, with
  no overflow, a ten-second pool checkout timeout and a ten-second connection timeout. These are
  typed settings rather than `.env.example` requirements; size them deliberately when deployment
  concurrency or the Supabase connection allowance changes.
- Prefer Supabase's Direct connection for these long-lived processes when the runtime has IPv6.
  Use the Session Pooler on port `5432` only for IPv4-only runtimes. Do not switch SQLAlchemy with
  asyncpg to Transaction Pooler port `6543` without separately validating prepared statements,
  transaction semantics and migration tooling.
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

Set server-only `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, a random
`FACEBOOK_WEBHOOK_VERIFY_TOKEN`, and an explicitly reviewed `FACEBOOK_GRAPH_API_VERSION`.
Configure Meta's callback at
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

### Meta App Review and Page verification

Perform this checklist manually with a non-production Page before enabling production traffic;
the automated suite never sends a live or paid request:

1. Confirm the configured app ID/secret and pinned Graph version belong to the reviewed Meta app.
2. Request/verify the permissions needed for Page subscription and messaging, including
   `pages_manage_metadata` and `pages_messaging`, and ensure the authorizing person has the Page
   `MESSAGE` task.
3. Configure the HTTPS callback `/api/v1/webhooks/facebook`, enter the server-only verify token,
   subscribe `messages`, and verify challenge plus signed text/image fixtures.
4. Connect the Page from the agent's Facebook tab. Confirm the UI reports healthy without ever
   displaying the submitted token; run **Kiểm tra lại** after permission changes.
5. Send one Page message and one bounded JPEG/PNG/WebP image from a tester account. Confirm one
   response job, one grounded reply, Graph acceptance and authenticated delivery receipt.
6. Verify exact opt-out (`stop`, `unsubscribe`, `dừng`, `hủy đăng ký`, `không nhận tin`) blocks
   automation, and exact opt-in (`start`, `subscribe`, `bắt đầu`, `đăng ký`, `nhận tin`) resumes it.
7. Verify a normal response is not sent after 24 hours. Do not configure message tags, marketing
   or proactive messaging for M1.2.
8. Reauthorize with a new token for the same Page and confirm the old Vault secret is revoked;
   verify a token for a different Page is rejected. Finally test local-first revoke.

## Zalo Official Account

Set server-only `ZALO_APP_ID`, `ZALO_APP_SECRET` and the exact
`ZALO_OAUTH_REDIRECT_URI`. Production callback URLs must use HTTPS. In Zalo Developers, register
the callback `/api/v1/channels/zalo/oauth/callback`, grant OA information/message permissions and
configure the webhook URL `/api/v1/webhooks/zalo`. Complete authorization from the chatbot's Zalo
tab, then copy the OA webhook signing secret into the write-only setup field; OAuth tokens are
never copied into AgentHub manually.

Manually verify authorization denial, same-OA reconnect, token refresh, signed text and attachment
events, duplicate delivery, the 48-hour reply boundary and local revocation with a non-production
OA. Do not enable broadcasts, templates, transactional, welcome, proactive or paid message
classes. Automated tests use fake gateways and must never call live Zalo authorization or message
APIs.

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
