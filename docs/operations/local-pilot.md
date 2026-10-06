# Local operations

F0-F5 are complete. This runbook remains the operational procedure for local development/pilot data; it is not a deployment guide.

## Health and logs

- `/health` and `/health/live` report process liveness without dependency details.
- `/health/ready` executes a PostgreSQL readiness check and returns `503` when unavailable; it does not call OpenAI, Qdrant or Storage.
- Responses include `X-Request-ID`.
- Access logs contain request ID, method, route template, status and duration only. Raw URLs/query strings, headers, bodies, messages, images, tokens, object keys and PII are prohibited.

## Retention

| Data | Local policy |
|---|---|
| Website visitor session/transcript | 24 hours |
| Unattached visitor image | 30 minutes |
| Attached visitor image | 1 hour |
| Consented lead | 30 days |
| Product-image grant | Recorded expiry |
| Website rate window | 2 hours |
| Usage event | Retained without content; conversation link may be cleared |

Run one bounded idempotent pass:

```powershell
pnpm ops:retention
```

The command revokes database access and removes expired transcript/contact content before private Storage cleanup. Failed Storage deletion remains `cleanup_pending` with a safe error and retries on the next pass. Do not manually mark failed rows deleted or erase their object keys.

## Knowledge operations

Create/verify an embedding profile without a paid embedding call:

```powershell
.\.venv\Scripts\python.exe -m agent_hub_api.knowledge.operator bootstrap-profile
.\.venv\Scripts\python.exe -m agent_hub_api.knowledge.operator activate-unprofiled --profile-id <PROFILE_ID> --workspace-id <WORKSPACE_UUID>
```

Rebuild/migration operations use a stable `--operation-id` so command retries do not create duplicate jobs. PostgreSQL is authoritative; Qdrant may be deterministically rebuilt from active generations.

## Backup boundary

PostgreSQL owns relational state, Supabase Storage owns uploaded objects and Qdrant is derived. A local restore rehearsal uses synthetic data and an isolated non-production target, verifies tenant/catalog/object state, rebuilds or restores compatible vectors, runs readiness/regressions and then removes the isolated target through provider-supported procedures.

Production backup, jurisdiction, TLS/domain and retention choices are deployment concerns and do not change the completed F0-F5 product status.
