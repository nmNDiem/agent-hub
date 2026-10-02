# Information architecture and routes

## Public/auth
`/login`, `/register`, `/forgot-password` and `/reset-password` (password recovery only once mail provider is configured); `/onboarding/create-shop`. Public widget assets live under a dedicated widget route, not inside the admin shell.

## Authenticated admin route proposal
```text
/app                         -> redirects to last permitted shop
/app/[workspaceSlug]/overview
/app/[workspaceSlug]/conversations
/app/[workspaceSlug]/conversations/[conversationPublicId]
/app/[workspaceSlug]/chatbots
/app/[workspaceSlug]/chatbots/new
/app/[workspaceSlug]/chatbots/[botPublicId]
/app/[workspaceSlug]/products
/app/[workspaceSlug]/knowledge
/app/[workspaceSlug]/knowledge/[documentId]
/app/[workspaceSlug]/channels     -> feature-gated
/app/[workspaceSlug]/analytics    -> feature-gated
/app/[workspaceSlug]/settings
```
Slug is navigation convenience, **not** authorization: backend resolves requested shop and verifies membership. Routes identify bots/conversations by canonical UUIDv7 `public_id`; internal BIGINT never appears in external URLs. Document details may use internal IDs only behind authenticated APIs, but prefer public IDs when shared links are expected.

## Sidebar sections
`Tổng quan`, `Hội thoại`, `Chatbot`, `Sản phẩm`, `Tri thức`, optional `Tài liệu` as filter/tab inside Tri thức; later `Kênh`, `Phân tích`; bottom `Cài đặt`, account menu. Simplify screenshot's long sidebar for MVP. Chatbot configuration and testing share the `/chatbots?agent=[botPublicId]` workbench; the former `/chatbots/[botPublicId]/playground` URL is redirect-only for backward compatibility. Do not include `Nâng cấp gói` promo until billing exists.

## Role-aware rendering
Member access is based on backend shop membership and capability, not hidden sidebar alone. Current roles are `owner`, `admin` and `member`: owners and admins may update workspace settings, while members have read access. Later domain actions must define their own role requirements. UI can hide actions for lack of capability, but the API always enforces authorization. Tenant switching cancels pending requests, changes URL and query keys, clears transient chat state, and checks whether the target shop exists and is permitted.

## Navigation acceptance
Deep-link to a selected chatbot via `?agent=` survives refresh; the legacy `/playground` link redirects without losing the selected bot; browser back preserves list filters; unauthenticated gets login + safe return URL; 403/404 have separate views; mobile Sheet closes on route change; active route recognizable without relying solely on color.
