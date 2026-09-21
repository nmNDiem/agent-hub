# Screen: Overview dashboard
Reference: `../../../assets/reference/01-admin-dashboard.png`.

## Goal
Owner understands genuine shop AI usage and accesses high-priority operations. No hardcoded 2,847 conversations, 96% rate, fake 3 channels, false sales uplift or dated chart from reference.

## Layout
- Page heading `Tổng quan`, period selector (7/30 days); shop context in topbar.
- KPI grid: conversations, bot replies, active bots, **genuinely** connected channels. If metric cannot be defined/calculated yet show `—` plus tooltip, not demo value.
- Conversation activity line chart (group by shop-local calendar date, timezone labelled). Big left chart + right `Sản phẩm được nhắc đến` if mentions actually tracked. Lower `Hội thoại gần đây`, `Tình trạng tri thức`, bot summary and channel status if implemented.
- Section titles and `Xem tất cả` links only when routes exist. Empty dashboard after first shop creation: empty illustration, `Tạo chatbot đầu tiên`, optional `Thêm sản phẩm`, no empty graph pretending usage.

## Data contract
`GET /api/v1/workspaces/{workspace_id}/dashboard?from=...&to=...` → cards/time series/list; server performs tenancy authorization. Cards define `total_conversations`, `assistant_messages`, `active_agents`, `connected_channels`; delta only if previous interval comparable. `GET .../conversations?limit=5` list preview. Analytics/top-product-mentions appear only once events support their accurate calculation (usually F5+).

## Interactions and errors
Period query in URL, chart tooltip supports keyboard or accessible table fallback, IDs copy raw UUIDv7. Loading skeleton same height as cards; 403 no data; partial endpoint failure does not blank entire dashboard. If no bots CTA opens bot wizard. Dates must not copy reference image May 2025.

## F1/F5 acceptance (F0: styled scaffold/empty shell only)
Authenticated and scoped to shop; cards sourced from DB; empty state accurate; shop switcher changes every card; KPI queries bounded and indexed; responsive stack; loading/error/empty tested. Chart may be omitted until the real time-series endpoint is ready—never invent it.
