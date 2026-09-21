# AgentHub

AgentHub là nền tảng AI-agent đa tenant và đa kênh. Deliverable đầu tiên là trợ lý bán hàng cho shop thời trang qua website widget.

Repository hiện ở **F0 Foundation**: FastAPI, Next.js dashboard, widget package scaffold, migration harness và CI. F0 chưa có authentication, tenant data, catalog, RAG, OpenAI integration hoặc widget chat hoạt động.

## Công nghệ và môi trường

| Layer | Decision |
|---|---|
| Frontend | Next.js 16 + TypeScript strict, Tailwind semantic tokens |
| Backend | Python 3.12 + FastAPI, SQLAlchemy async + Alembic |
| Database | Supabase PostgreSQL |
| File storage | Supabase Storage |
| Authentication | FastAPI-managed email + password, **not** Supabase Auth |
| LLM provider | OpenAI (exact chat/vision/embedding models are configuration decisions) |
| Current runtime | Local development |
| Future runtime | Docker containers on a VPS; Supabase remains hosted DB/Storage |
| Initial channel/use case | Embedded website chat for fashion shops |
| IDs | UUIDv7 selectively + BIGINT IDENTITY internally; see `docs/architecture/identifiers.md` |
| Package manager | pnpm 10.33.0, Node.js 24 |
| UI reference | Three mockups + design system under `docs/design/` and `assets/reference/` |

## Cấu trúc F0

```text
apps/
  api/       FastAPI, tests và Alembic
  web/       Next.js admin scaffold
  widget/    TypeScript package scaffold, chưa có chat runtime
docs/        Product, architecture và design source of truth
assets/      Reference images, không phải production catalog assets
```

## Cài đặt

```powershell
pnpm install --frozen-lockfile
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\apps\api[dev]"
Copy-Item .env.example .env
Copy-Item apps\web\.env.example apps\web\.env.local
```

Không điền secret thật vào file được commit. `AGENT_HUB_DATABASE_URL`, Supabase keys, OpenAI key và JWT key đều là server-only.

## Chạy local

Terminal API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn agent_hub_api.main:app --app-dir apps\api\src --host 127.0.0.1 --port 8000
```

Kiểm tra liveness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Terminal web:

```powershell
pnpm dev:web
```

Mở `http://127.0.0.1:3000`. Thẻ FastAPI trên dashboard chỉ báo “Đang hoạt động” khi lấy được phản hồi thật từ API.

## Quality gates

Frontend và widget:

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Backend:

```powershell
Set-Location apps\api
ruff check .
mypy
pytest
alembic upgrade head --sql
```

Lệnh Alembic trên là offline dry-run và không cần database. Online migration yêu cầu `AGENT_HUB_DATABASE_URL` trong environment:

```powershell
Set-Location apps\api
$env:AGENT_HUB_DATABASE_URL = "postgresql+asyncpg://..."
alembic upgrade head
```

Baseline F0 cố ý không tạo domain table. Schema identity/tenant chỉ được tạo trong F1 sau khi phase đó được phê duyệt.

## Where to read first

1. `AGENTS.md` — Codex rules and implementation boundaries.
2. `docs/00-decisions.md` — confirmed vs proposed vs deferred; no superseding owner decisions.
3. `docs/12-full-product-scope.md` — entire planned system and boundaries.
4. `docs/03-architecture.md` and `docs/13-target-architecture.md` — MVP/current vs full-system design.
5. `docs/09-roadmap.md`, `docs/22-phase-gates.md`, `docs/10-codex-backlog.md` — plan vs permission to implement.
6. `docs/design/README.md` and `assets/reference/` — UI guidance for Codex (screenshots are illustrative).
7. `docs/architecture/README.md` — technical implementation detail; numbered master docs remain the authority for naming/routes/phases.
8. `docs/23-decision-and-change-control.md` — how to resolve changes without silently changing architecture.

## Document directory

| File | Purpose |
|---|---|
| `docs/00-decisions.md` | Owner decisions; proposals; exclusions |
| `docs/01-product-vision.md` | Product vision |
| `docs/02-product-requirements.md` | Fashion-shop MVP requirements |
| `docs/03-architecture.md` | Core system and local-to-VPS design |
| `docs/04-data-model.md` | MVP data entities |
| `docs/05-api-contract.md` | MVP API and SSE outline |
| `docs/06-agent-and-rag.md` | Agent, tools, retrieval and image input |
| `docs/07-ux-flows.md` | MVP user journeys |
| `docs/08-security.md` | Auth, tenant separation, AI safety |
| `docs/09-roadmap.md` | MVP delivery sequence |
| `docs/10-codex-backlog.md` | Executable MVP work items |
| `docs/11-acceptance-test-plan.md` | MVP quality gates |
| `docs/12-full-product-scope.md` | Full AgentHub product scope |
| `docs/13-target-architecture.md` | Target modular architecture |
| `docs/14-channel-platform.md` | Channels, webhooks, adapters |
| `docs/15-saas-and-billing.md` | Tenancy, quota, plans, subscriptions |
| `docs/16-commerce-domain.md` | Fashion/shop commerce domain |
| `docs/17-operations-deployment.md` | Local, Docker/VPS and operations |
| `docs/18-data-privacy-retention.md` | Data lifecycle and retention |
| `docs/19-agent-lifecycle.md` | Agent identity, publish and policy |
| `docs/20-full-system-api-contracts.md` | Future APIs and event patterns |
| `docs/21-full-system-test-strategy.md` | Cross-cutting and E2E testing |
| `docs/22-phase-gates.md` | Phase sequencing and exit criteria |
| `docs/23-decision-and-change-control.md` | Open decisions and ADR discipline |

**Merged-spec rule:** `docs/00-decisions.md`, `docs/05-api-contract.md`, `docs/09-roadmap.md`, `docs/10-codex-backlog.md` and `docs/22-phase-gates.md` govern decisions, HTTP routes and phase numbering; `docs/architecture/` expands details, and `docs/design/` governs UI. `workspace` = fashion UI shop; `agent` = UI chatbot.

## Additional folders

- `docs/design/` — tokens, components, 7 screen specs, flows, accessibility, visual QA.
- `docs/architecture/` — UUIDv7/BIGINT convention, detailed data and security, RAG, ingestion, frontend, SQL **reference**, testing/deployment.
- `assets/reference/` — dashboard, playground, web widget reference images; no right to reuse sample product imagery.

## First Codex instruction

Read `AGENTS.md`, `docs/00-decisions.md`, `docs/03-architecture.md`, and `docs/10-codex-backlog.md`. Implement **F0 only** under `docs/10-codex-backlog.md` (scaffold only). Read `docs/design/README.md` and `docs/architecture/README.md`; use the reference images for styling the scaffold. Scaffold Next.js/TypeScript, FastAPI, local run scripts and secure env templates. Do not provision VPS, implement payment flows, add other LLM providers or claim production readiness. Report actual tests and commands.
