# Component specifications

| Component | Props/data | Required behaviour |
|---|---|---|
| `AppShell` | shop, nav, user | fixed desktop nav; mobile Sheet; main landmark; skip-to-content |
| `ShopSwitcher` | accessible shops, active shop | switches scope, invalidates old-shop queries, resets filters, never carries old conversation into new shop |
| `AppTopbar` | current route, notifications | accessible search trigger; no fake notifications in F0 |
| `MetricCard` | label, value, unit, delta?, loading | trend shown only if backed by real timeseries; fallback `—`; accessible numeral |
| `StatusBadge` | stable status enum | status text + style; never color alone |
| `DataTable` | rows, sort, filters, cursor | URL-persisted filters, keyboard, empty/error/loading; server paging for large lists |
| `ProductCard` | image?, name, price?, availability?, link | correct aspect ratio, fallback image, no price or availability invented |
| `CopyId` | canonical `public_id` | visually ellipsized, copy exact ID, toast success/error, keyboard accessible |
| `ConversationListItem` | preview, channel, timestamp, state | active row + unread; no unsafe content in preview |
| `ChatBubble` | role, text/attachments, state | stream partial text safely, markdown sanitization, preserve user-authored newlines |
| `ChatProductCarousel` | 0–N product matches | arrow + keyboard scroll, cards open approved product URL; empty list hidden |
| `SourceChip` | retrieved chunk metadata | opens sourced detail only when backend returns source; no invented sources |
| `UploadDropzone` | accepted types/sizes, progress | type/size validation client and server, progress, cancel/retry/error |
| `WidgetLauncher` | bot branding, unread | position, focus return, minimization, badge only for real unread message |
| `ConfirmDialog` | action summary, danger | delete/archive explicit, disabled while pending, server error recoverable |

## UI states mandatory on all async surfaces
`idle | loading | ready | empty | error | forbidden`; mutation adds `submitting | success`. Every async list has real skeleton; failure has retry with preserved form data; empty has action; forbidden says access is not permitted; distinguish 404 from unauthorized. For streaming: `connecting | streaming | finished | canceled | failed`; on error retain already displayed response and allow retry.

## Shell and navigation expectations
Never display future modules as functional. F0 may show navigable, clearly labeled scaffold/empty shell only; F1+ reveal real authenticated pages when implemented; future Channels badges `Sắp ra mắt` and no clickable fake connection states. Global search `⌘K` is not active until search backend exists; make command menu navigation-only initially or hide placeholder.

## Chat rendering
Plain text by default; if markdown enabled sanitize HTML, prohibit script/style and dangerous URL schemes, external link `rel="noopener noreferrer"`; all model-provided links require domain validation. Stream into a single message block, avoid reflow on every token by batching updates. Product suggestions use structured backend `products[]`, never regex parse arbitrary LLM text to invent IDs. Render citations only for real retrieved source IDs and permitted view.

## Forms
Field label + help + inline error; `aria-describedby`, disabled state, explicit unsaved-changes affordance. Save action is sticky only when page long; optimistic updates only for reversible settings, with rollback and toast. Destructive changes use confirmation.
