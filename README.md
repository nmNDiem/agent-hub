# AgentHub

AgentHub is a multi-tenant, omnichannel AI-agent platform. Its completed foundation is a fashion-shop assistant with catalog-grounded answers, private knowledge/RAG, a Website widget, visitor image input, leads, conversation history, usage controls and local operations. The current product delivery adds Facebook Messenger, Zalo and a unified human operating workflow.

## Stack

| Layer | Technology |
|---|---|
| Dashboard | Next.js 16, TypeScript strict, Tailwind semantic tokens |
| Widget | Independent TypeScript/Vite bundle with Shadow DOM isolation |
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| Database | Supabase PostgreSQL |
| Storage | Supabase Storage |
| Vector index | Qdrant; PostgreSQL remains authoritative for knowledge/chunks |
| Authentication | FastAPI-owned email/password; not Supabase Auth |
| AI | OpenAI generation, vision and embeddings behind adapters |
| Package manager | pnpm 10.33.0, Node.js 24 |

## Repository

```text
apps/
  api/       FastAPI modular monolith, migrations and tests
  web/       Next.js admin application
  widget/    Independent embeddable Website widget
docs/        Current product/engineering documentation
assets/      Visual references, not production catalog assets
```

Start reading at [`docs/README.md`](docs/README.md). It provides minimal task-specific reading routes so contributors and AI agents do not load the full documentation set. Historical specifications remain available through Git history rather than the working tree.

## Install

```powershell
pnpm install --frozen-lockfile
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
```

Never commit real secrets. Database, Supabase, Qdrant, OpenAI, signing and future channel credentials are server-only. Stable limits and TTLs live in typed application configuration; `.env.example` contains only placeholders and deployment-specific values.

## Run locally

Apply migrations, then start API and web:

```powershell
pnpm db:migrate
pnpm dev
```

Open `http://127.0.0.1:3000`. Individual processes are available through `pnpm dev:api`, `pnpm dev:web` and `pnpm dev:worker` when their providers are configured.

Build and serve the Widget loader for an external local embed page:

```powershell
pnpm dev:widget
```

This serves `http://127.0.0.1:4173/widget/v1/loader.js`.

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

See [`docs/operations.md`](docs/operations.md) for setup, provider notes and command boundaries. Automated chatbot checks must not incur paid service calls; the owner runs explicitly budgeted provider checks manually.

## Documentation model

- [`docs/product.md`](docs/product.md): complete product capabilities.
- [`docs/decisions.md`](docs/decisions.md): confirmed owner decisions and genuinely open implementation details.
- [`docs/architecture.md`](docs/architecture.md): system topology and domain boundaries.
- [`docs/security.md`](docs/security.md): mandatory security/privacy invariants.
- [`docs/roadmap.md`](docs/roadmap.md): delivery order; M1 Omnichannel Operations is current.
- `docs/domains/`: behavior by business domain.
- [`docs/data-model.md`](docs/data-model.md), [`docs/api.md`](docs/api.md) and [`docs/testing.md`](docs/testing.md): technical contracts.
- [`docs/ui.md`](docs/ui.md): interface and accessibility guidance.
- [`docs/operations.md`](docs/operations.md): local setup and operating procedures.
- `docs/tasks/`: only currently approved implementation specifications.
