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

Individual services use `pnpm dev:api`, `pnpm dev:web`, `pnpm dev:worker` and `pnpm dev:widget` when their dependencies are configured. Use only isolated development PostgreSQL/Storage/Qdrant resources; secrets remain server-only.

## Health, logs and retention

- `/health/live` checks the process. `/health/ready` checks PostgreSQL and avoids paid providers.
- Logs contain request ID, method, route template, status and duration only—never raw URL/query, headers, bodies, messages, images, tokens, object keys or PII.
- Local retention: Website session/transcript 24 hours, unattached image 30 minutes, attached image one hour and consented lead 30 days.
- Run a bounded idempotent cleanup pass with `pnpm ops:retention`. It revokes database access before Storage deletion; failed deletion remains retryable.

PostgreSQL owns relational state, Supabase Storage owns uploaded objects and Qdrant is derived/rebuildable. Restore rehearsal uses synthetic data in an isolated non-production target.

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
