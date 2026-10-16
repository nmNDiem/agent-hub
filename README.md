# AgentHub

AgentHub is a multi-tenant platform for creating, configuring, equipping, deploying and operating AI agents across domains. Its completed first vertical is a fashion-commerce assistant with structured catalog grounding, private Knowledge/RAG, Website/Facebook/Zalo channels, unified conversations, contacts and operational analytics. Commerce is an optional domain capability, not the definition of AgentHub.

## Stack

| Layer | Technology |
|---|---|
| Dashboard | Next.js 16, strict TypeScript, Tailwind semantic tokens |
| Widget | Independent TypeScript/Vite bundle with Shadow DOM isolation |
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| Database | Supabase PostgreSQL |
| Storage | Supabase Storage |
| Vector index | Qdrant; PostgreSQL remains authoritative |
| Authentication | FastAPI-owned email/password; not Supabase Auth |
| AI | OpenAI generation, vision and embeddings behind adapters |
| Package manager | pnpm 10.33.0, Node.js 24 |

## Repository

```text
apps/
  api/       FastAPI modular monolith, migrations and tests
  web/       Next.js administration application
  widget/    Independent embeddable Website widget
docs/        Current product and engineering authority
assets/      Visual references, not production data
```

Start with [`AGENTS.md`](AGENTS.md) and [`docs/README.md`](docs/README.md). Historical specifications are context in Git history, not current authority.

## Install and run

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

Open `http://127.0.0.1:3000`. Use `pnpm dev:api`, `pnpm dev:web`, `pnpm dev:worker`, `pnpm dev:channel-worker` and `pnpm dev:widget` for individual processes where configured.

## Quality commands

Frontend and Widget:

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

PostgreSQL integration tests are opt-in and recreate only `agenthub_test` in a local/test database:

```powershell
$env:RUN_POSTGRES_INTEGRATION_TESTS="true"
pytest -m postgres
Remove-Item Env:RUN_POSTGRES_INTEGRATION_TESTS
```

See [`docs/operations.md`](docs/operations.md) for environment and provider procedures. Automated verification must not incur paid provider calls.
