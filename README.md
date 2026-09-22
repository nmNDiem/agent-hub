# AgentHub

AgentHub là nền tảng AI-agent đa tenant và đa kênh. Deliverable đầu tiên là trợ lý bán hàng cho shop thời trang qua website widget.

Repository đã có nền tảng xác thực và tenant cùng product/variant/size-guide CRUD, CSV preview/import idempotent, ảnh riêng tư trên Supabase Storage và catalog UI. RAG, OpenAI integration và widget chat chưa được triển khai.

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

## Cấu trúc hiện tại

```text
apps/
  api/       FastAPI modular monolith: core, identity, workspaces, tests và Alembic
  web/       Next.js app routes, shared UI/lib và auth/workspace feature modules
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

Không điền secret thật vào file được commit. `DATABASE_URL`, Supabase keys, OpenAI key và `JWT_SIGNING_KEY` đều là server-only. JWT key phải có ít nhất 32 byte ngẫu nhiên. Giữ `EMAIL_DELIVERY_ENABLED=false` cho tới khi backend có provider gửi mail thật.

## Chạy local

```powershell
pnpm dev
```

Mở `http://127.0.0.1:3000`. Nhấn `Ctrl+C` để dừng cả API và web. Thẻ FastAPI trên dashboard chỉ báo “Đang hoạt động” khi lấy được phản hồi thật từ API.

Để chạy riêng từng service, dùng `pnpm dev:api` hoặc `pnpm dev:web`.

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

Lệnh Alembic trên là offline dry-run và không cần database. Online migration yêu cầu `DATABASE_URL` trong environment:

```powershell
pnpm db:migrate
```

Các migration tạo identity/tenant tables, sau đó tạo `products`, `product_variants`, `size_guides`, `product_images` và `catalog_imports`. Chạy migration online trên development database trước khi thử catalog:

```powershell
pnpm db:migrate
```

Sau đó mở `http://127.0.0.1:3000/register`. Access/refresh token nằm trong cookie HttpOnly; trình duyệt không lưu bearer token trong localStorage. Để upload/xem ảnh catalog, tạo private bucket `agent-hub-private` trong Supabase Storage và cấu hình `SUPABASE_URL` cùng `SUPABASE_SERVICE_ROLE_KEY` chỉ ở backend. CRUD sản phẩm và CSV vẫn hoạt động khi Storage chưa được cấu hình; thao tác ảnh sẽ trả lỗi 503 rõ ràng.

CSV catalog dùng header:

```text
product_sku,name,description,category,currency,price,product_url,variant_sku,variant_name,color,size,variant_price,stock_quantity
```

Một `product_sku` có thể xuất hiện trên nhiều dòng để nhóm variants; `variant_sku` không được trùng. Import là create-only và transactional, không tự ghi đè SKU hiện hữu hoặc đã archived.

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
| `docs/12-full-product-scope.md` | Full product scope |
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

## Current Codex instruction

Read `AGENTS.md`, `docs/00-decisions.md`, `docs/03-architecture.md`, and the acceptance criteria for the explicitly requested task. Foundation, authentication, tenancy and catalog capabilities are implemented; do not implement knowledge/RAG, agent runtime, widget chat or later capabilities without a new owner request. Preserve the domain-oriented modular monolith under `agent_hub_api`, tenant isolation, the published API contract and the database schema unless the approved task explicitly changes them. Read `docs/design/README.md` for UI work and `docs/architecture/README.md` for implementation boundaries. Do not provision VPS, implement payment flows, add other LLM providers or claim production readiness. Report actual tests and commands.
