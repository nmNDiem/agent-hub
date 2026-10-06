# Navigation and flows

## Information architecture

```text
/app/[workspaceSlug]/overview
/app/[workspaceSlug]/inbox
/app/[workspaceSlug]/inbox/[conversationPublicId]
/app/[workspaceSlug]/contacts
/app/[workspaceSlug]/agents
/app/[workspaceSlug]/products
/app/[workspaceSlug]/knowledge
/app/[workspaceSlug]/channels
/app/[workspaceSlug]/analytics
/app/[workspaceSlug]/settings
```

Existing routes remain compatible until an approved task migrates them. A workspace slug is navigation convenience, not authorization. External conversation and agent routes use UUIDv7 public IDs; private internal BIGINT IDs are not exposed to visitors.

## Primary navigation

`Tổng quan`, `Hộp thư`, `Khách hàng`, `Chatbot`, `Sản phẩm`, `Tri thức`, `Kênh`, `Phân tích`, then `Cài đặt`. A route appears as functional only when its backend capability exists. During incremental M1 delivery, unavailable sub-features use an honest unavailable state rather than fake provider data.

## Main journeys

### Configure and publish

`Register -> create workspace -> add catalog/knowledge -> create agent -> test Playground -> publish -> configure channel -> verify connection -> receive conversation`

### Customer conversation

`provider/Website message -> verified scoped inbound -> normalized conversation -> AI answer or human workflow -> channel delivery -> operator-visible result`

### Human handoff

`AI/visitor requests help -> thread marked pending/handoff -> operator accepts assignment -> automation pauses -> human replies -> resolve or deliberately resume AI`

### Improve operations

`review inbox/analytics -> identify unresolved/failure pattern -> correct data/config/process -> verify -> measure later outcome`

## Navigation rules

- Workspace switching cancels pending requests and clears old scoped caches/transient drafts.
- URL filters persist for lists and browser back/forward.
- Mobile navigation closes after route change and returns focus predictably.
- 403 and 404 have distinct safe views.
- Active state is not conveyed by color alone.
