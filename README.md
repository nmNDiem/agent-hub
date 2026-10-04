# AgentHub

AgentHub là nền tảng AI-agent đa tenant và đa kênh. Deliverable đầu tiên là trợ lý bán hàng cho shop thời trang qua website widget.

Repository đã có nền tảng xác thực và tenant, generic catalog CRUD/import/location scope, knowledge/RAG, grounded agent runtime, Playground, publish revision bất biến, kênh Web và website widget có chat văn bản/ảnh. Widget dùng anonymous session theo origin, SSE, product card lấy dữ kiện từ catalog và private Storage cho ảnh khách gửi.

## Công nghệ và môi trường

| Layer | Decision |
|---|---|
| Frontend | Next.js 16 + TypeScript strict, Tailwind semantic tokens |
| Backend | Python 3.12 + FastAPI, SQLAlchemy async + Alembic |
| Database | Supabase PostgreSQL |
| File storage | Supabase Storage |
| Vector index | Qdrant; Postgres remains the authoritative knowledge/chunk store |
| Authentication | FastAPI-managed email + password, **not** Supabase Auth |
| Model providers | OpenAI for MVP generation/vision/embeddings behind provider-neutral interfaces; exact model IDs remain configuration decisions |
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
  widget/    TypeScript bundle độc lập: Shadow DOM, SSE chat, ảnh và product cards
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

Không điền secret thật vào file được commit. `DATABASE_URL`, Supabase keys, Qdrant key, OpenAI key và `JWT_SIGNING_KEY` đều là server-only. JWT key phải có ít nhất 32 byte ngẫu nhiên. `.env.example` chỉ liệt kê secret và giá trị phụ thuộc môi trường triển khai; token TTL, tên bucket mặc định, giới hạn catalog/import/knowledge/agent runtime, thời hạn signed URL và job lease dùng default tập trung trong `apps/api/src/agent_hub_api/core/config.py`. Chỉ đặt biến môi trường tương ứng khi chủ động override các default đó. Email delivery mặc định tắt trong config và chỉ được override sau khi backend có provider gửi mail thật. Qdrant Cloud được cấu hình cho non-production development; ingestion thật cần explicit embedding model/dimensions, còn generation thật cần explicit `GENERATION_MODEL`. Mẫu local dùng `gpt-6-luna`; adapter tự động gửi `reasoning_effort="none"` để function calling hoạt động qua Chat Completions. Hệ thống vẫn từ chối khởi động generation khi thiếu model ID.

## Chạy local

```powershell
pnpm dev
```

Mở `http://127.0.0.1:3000`. Nhấn `Ctrl+C` để dừng cả API và web. Thẻ FastAPI trên dashboard chỉ báo “Đang hoạt động” khi lấy được phản hồi thật từ API.

Để chạy riêng từng service, dùng `pnpm dev:api` hoặc `pnpm dev:web`. Widget loader cần được build rồi phục vụ ở origin khớp `WIDGET_PUBLIC_BASE_URL`; local preview dùng:

```powershell
pnpm dev:widget
```

Lệnh này build và phục vụ `http://127.0.0.1:4173/widget/v1/loader.js`. Giữ terminal đó chạy khi kiểm thử embed local.

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

Critical PostgreSQL integration tests reuse `DATABASE_URL` but isolate all objects in the exact schema `agenthub_test`. They drop and recreate that schema, migrate it, and clean it afterward, so opt in only against a local/test database:

```powershell
$env:RUN_POSTGRES_INTEGRATION_TESTS="true"
pytest -m postgres
Remove-Item Env:RUN_POSTGRES_INTEGRATION_TESTS
```

The suite refuses to run unless `APP_ENV` is `local` or `test`. It never uses or drops `public`.

Lệnh Alembic trên là offline dry-run và không cần database. Online migration yêu cầu `DATABASE_URL` trong environment:

```powershell
pnpm db:migrate
```

Các migration tạo identity/tenant tables, catalog canonical, generic options, location/collection scope, agent configuration/assignments, immutable published revisions, knowledge versions/generations/jobs, widget sessions/conversations/messages/images/rate limits và import staging/issues/mapping profiles. Chạy migration online trên development database trước khi thử catalog, agent, knowledge hoặc widget APIs:

```powershell
pnpm db:migrate
```

Sau đó mở `http://127.0.0.1:3000/register`. Access/refresh token nằm trong cookie HttpOnly; trình duyệt không lưu bearer token trong localStorage. Để upload/xem ảnh catalog, tạo private bucket `agent-hub-private` trong Supabase Storage và cấu hình `SUPABASE_URL` cùng `SUPABASE_SERVICE_ROLE_KEY` chỉ ở backend. CRUD sản phẩm và CSV vẫn hoạt động khi Storage chưa được cấu hình; thao tác ảnh sẽ trả lỗi 503 rõ ràng.

Knowledge nhận manual text hoặc PDF/TXT private qua API, nhưng parsing/embedding không chạy trong process FastAPI. Job được lưu bền vững để worker riêng claim bằng lease + fencing token. Worker dùng concrete OpenAI/Qdrant adapters khi runtime thật và fake adapters trong test; không khởi động worker trước khi embedding profile đã được operator xác minh/kích hoạt. PDF dùng strict `pypdf==6.19.0` trong subprocess giới hạn CPU/RAM/thời gian; PDF mã hóa và scan ảnh không OCR trả error code riêng.

Importer mới nhận CSV, XLS và XLSX, tự suy luận cấu trúc từ header/row shape, hỗ trợ nhiều sheet và không yêu cầu chọn vendor. Luồng mới là `Upload → Analyze → Resolve (nếu cần) → Preview diff → Commit`.

Import mặc định là `MERGE`: dữ liệu không có trong file không bị archive/delete; cột thiếu không xóa giá trị hiện hữu. Hai route CSV cũ vẫn được giữ cho client cũ. Header CSV cũ là:

```text
product_sku,name,description,category,currency,price,product_url,variant_sku,variant_name,color,size,variant_price,stock_quantity
```

Một `product_sku` có thể xuất hiện trên nhiều dòng để nhóm variants; `variant_sku` không được trùng. Chi tiết model, semantics và API mới nằm tại `docs/catalog-import.md`.

## F3.3 embedding và Qdrant retrieval

Backend đã có concrete OpenAI embedding adapter và Qdrant Cloud adapter. PostgreSQL vẫn là nguồn dữ liệu authoritative; mỗi truy vấn Qdrant bắt buộc có `workspace_id`, allowed knowledge-base IDs và embedding profile do server đưa vào, sau đó mọi point/citation được revalidate lại với active generation trong PostgreSQL.

Qdrant Cloud có thể được kiểm chứng mà không gọi OpenAI. Test tạo một collection ngẫu nhiên chứa `_test_`, dùng vector deterministic, rồi chỉ xóa đúng collection đó:

```powershell
Set-Location apps\api
$env:RUN_QDRANT_INTEGRATION_TESTS="true"
pytest -m qdrant tests/test_qdrant_integration.py
Remove-Item Env:RUN_QDRANT_INTEGRATION_TESTS
Set-Location ..\..
```

Để tạo profile thật, operator phải điền rõ `EMBEDDING_MODEL` và `EMBEDDING_DIMENSIONS`; hệ thống không đoán hoặc seed model. Lệnh bootstrap chỉ kiểm tra/tạo Qdrant collection và lưu immutable profile, không gọi OpenAI:

```powershell
.\.venv\Scripts\python.exe -m agent_hub_api.knowledge.operator bootstrap-profile
.\.venv\Scripts\python.exe -m agent_hub_api.knowledge.operator activate-unprofiled --profile-id <PROFILE_ID> --workspace-id <WORKSPACE_UUID>
```

Worker riêng chỉ chạy khi `OPENAI_API_KEY`, Database, Supabase Storage và Qdrant đều đã được cấu hình:

```powershell
pnpm dev:worker
```

Các operator command còn lại là `rebuild`, `start-migration` và `promote`. Mỗi rebuild/migration yêu cầu `--operation-id` ổn định để retry command không tạo job trùng. Profile cũ được giữ cho rollback có kiểm soát, nhưng point cũ không thể đi qua active-generation revalidation sau cutover.

## F3.4 grounded agent runtime

Runtime nội bộ kết hợp retrieval đã revalidate với ba catalog tool tenant-safe. OpenAI chỉ được gọi qua `ModelGateway`; model phải dùng sequential tool calls và `submit_grounded_answer`. Model tạo lời thoại channel-neutral đã qua validation, còn product card được backend dựng từ catalog result hiện thời; SKU/giá/tồn kho và các dữ kiện thương mại không được parse từ model prose. Web hiển thị card, còn channel adapter tương lai có thể render cùng structured result thành text hoặc native template. Knowledge answer chỉ nhận source alias đã thực sự retrieve và từng đoạn phải là extractive excerpt của source đó; prompt/document và agent instructions đều được đóng gói như untrusted data dưới platform policy cố định.

Mỗi lượt bị giới hạn question/context/tool-result chars, output/total tokens, model calls, tool calls và số catalog result. `NULL` inventory tiếp tục là `unknown`; generic options/attributes và product-only records không cần fashion-only fields. Automated tests dùng fake gateway, không phát sinh paid OpenAI request.

## F3.5 knowledge dashboard and Playground

Dashboard có route `Tri thức` để tạo knowledge base, nhập nội dung thủ công, tải PDF/TXT, theo dõi ingestion, thử lại lỗi và thu hồi tài liệu. Route `Chatbot` quản lý cấu hình bản nháp, catalog scope và knowledge assignments. Owner/admin được ghi; member chỉ đọc theo quyền backend.

Playground dùng endpoint SSE có auth + CSRF, gọi đúng grounded runtime F3.4. Transcript chỉ tồn tại cục bộ, history gửi lên bị giới hạn và coi là untrusted data. Server kiểm chứng lời thoại cùng mọi product/source reference trước khi phát `message.delta`, `product.cards` và `source.refs`; không chuyển tiếp raw provider output chưa qua validation. Stop hủy request và giữ phần text đã nhận. Nếu thiếu OpenAI/Qdrant, UI nhận trạng thái `AGENT_RUNTIME_DISABLED` thay vì response giả.

## Website widget và vision

Dashboard Chatbot có bảng `Kênh Web` để cấu hình exact allowed origins, màu thương hiệu/vị trí launcher, kiểm tra readiness, preview, publish/pause và sao chép embed snippet. Publish tạo revision bất biến; phiên khách luôn khóa vào revision đã publish, workspace và origin do server xác minh.

Bundle `apps/widget` là IIFE nhẹ, dùng Shadow DOM và bảo vệ host styles để nhúng vào trang ngoài mà không kéo theo React/dashboard runtime. Anonymous session token chỉ giữ trong `sessionStorage`/memory, không nằm trong DOM hoặc URL. Widget hỗ trợ transcript cùng phiên, SSE, stop/reset, product/source cards, protected product images và responsive keyboard-accessible UI.

Ảnh JPEG/PNG/WebP được kiểm tra chữ ký/decoded format, giới hạn 5 MiB và 20 megapixel, re-encode để bỏ metadata rồi lưu private. Attachment handle theo session chỉ dùng một lần; vision dùng adapter/model riêng và không fallback sang text hay suy đoán đặc điểm cá nhân. Automated tests dùng fake adapters, không gọi dịch vụ trả phí. Lead capture, owner inbox/usage và tác vụ dọn dữ liệu hết hạn thuộc F5.

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

Read `AGENTS.md`, `docs/00-decisions.md`, `docs/03-architecture.md`, and the acceptance criteria for the explicitly requested task. Foundation through website widget/vision are implemented locally; do not implement F5 operations, VPS rollout, social channels, payments or other providers without a new owner request. Preserve the domain-oriented modular monolith under `agent_hub_api`, tenant isolation, the published API contract and the database schema unless the approved task explicitly changes them. Read `docs/design/README.md` for UI work and `docs/architecture/README.md` for implementation boundaries. Do not claim production readiness. Report actual tests and commands.
