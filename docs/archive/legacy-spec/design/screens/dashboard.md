# Screen: Overview dashboard
Reference: `../../../assets/reference/01-admin-dashboard.png`.

## Goal
Owner understands genuine shop AI usage and accesses high-priority operations. No hardcoded 2,847 conversations, 96% rate, fake 3 channels, false sales uplift or dated chart from reference.

## Layout
- Page heading `Tổng quan`, period selector (7/30 days); shop context in topbar.
- KPI grid: conversations started in the selected period, completed bot replies in the selected period, published chatbots with Web enabled, and generated turns used/remaining in the workspace-local calendar month.
- Conversation activity line chart groups newly started conversations by shop-local calendar date and labels the timezone. Lower cards show real recent conversations and consented leads. Product mentions remain absent because they are not tracked as an aggregate.
- Section titles and `Xem tất cả` links only when routes exist. Empty dashboard after first shop creation: empty illustration, `Tạo chatbot đầu tiên`, optional `Thêm sản phẩm`, no empty graph pretending usage.

## Data contract
`GET /api/v1/workspaces/{workspace_id}/dashboard?days=7|30` returns bounded cards, shop-local daily activity, recent conversation/lead summaries and monthly usage after owner/admin authorization. `active_agents` and `enabled_web_channels` currently count published agents with their one enabled Web channel. `GET .../usage` returns persisted generation/vision calls, tools, tokens and generated-turn quota state without cost estimates.

## Interactions and errors
The 7/30-day selector reloads real data; the chart has an accessible table fallback. Loading, empty, error and forbidden states never substitute mock data. Dates must not copy reference image May 2025.

## Dashboard acceptance
Authenticated and scoped to shop; cards sourced from DB; empty state accurate; shop switcher changes every card; KPI queries bounded and indexed; responsive stack; loading/error/empty tested. Chart may be omitted until the real time-series endpoint is ready—never invent it.
