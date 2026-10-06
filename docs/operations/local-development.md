# Local development

## Prerequisites and install

Repository versions are authoritative. Current baseline is Node.js 24, pnpm 10.33.0 and Python 3.12.

```powershell
pnpm install --frozen-lockfile
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
```

Use isolated development Supabase PostgreSQL/Storage and Qdrant resources. Never put live customer data or real secrets in committed files. OpenAI, Supabase, Qdrant, database and signing credentials are server-only.

## Start

Apply online migrations to the configured development database:

```powershell
pnpm db:migrate
```

Start API and web:

```powershell
pnpm dev
```

Start individual services with `pnpm dev:api`, `pnpm dev:web` and `pnpm dev:worker` where configured. Build/serve the local widget loader with:

```powershell
pnpm dev:widget
```

The widget loader is then available at `http://127.0.0.1:4173/widget/v1/loader.js` for an external static-host embed check.

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

Critical PostgreSQL tests are opt-in, require `APP_ENV=local|test`, recreate only the `agenthub_test` schema in the configured non-production database and clean it afterward:

```powershell
$env:RUN_POSTGRES_INTEGRATION_TESTS="true"
pytest -m postgres
Remove-Item Env:RUN_POSTGRES_INTEGRATION_TESTS
```

Qdrant integration tests use an explicitly configured non-production service and their own random test collection. Do not run paid OpenAI/chatbot checks automatically; the owner performs those manually with a declared budget.

## Configuration rules

- `.env.example` contains only secret placeholders, deployment-specific endpoints/resource names and values without a safe default.
- Stable limits, TTLs and pipeline defaults live in typed backend configuration.
- Do not start real ingestion until an embedding model/dimension profile is explicitly verified and activated.
- `GET /health/live` checks the process; `GET /health/ready` checks PostgreSQL only and avoids paid providers.
