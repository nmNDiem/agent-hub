# UI and interaction

## Direction

AgentHub uses a compact, approachable SaaS control panel with neutral light surfaces, clear hierarchy and real data. Lagoon is the default palette; Aurora and Ember are allowlisted alternatives. [`ui-tokens.json`](ui-tokens.json) is the machine-readable token source. The Website widget uses independent workspace branding.

The current interface language is Vietnamese. Format numbers, currency and time from actual locale/workspace data. Never copy products, people, dates, IDs, metrics or Facebook/Zalo connection states from reference images.

## Information architecture

Primary areas are Overview, Inbox, Contacts, Agents, Catalog, Knowledge, Channels, Analytics and Settings. Existing routes remain compatible until their approved task migrates them. Workspace slugs and public IDs are navigation identifiers, not authorization.

The selected agent uses one workbench for configuration, Playground, publishing and channel assignment. Catalog import follows `Analyze -> Resolve -> Review diff -> Commit`. The unified inbox presents Website/Facebook/Zalo threads through the same list/detail workflow, with explicit AI/human mode, assignment, unread, status, notes, tags and delivery state as M1 lands.

## Shared behavior

- Every async surface supports loading, ready, empty, error and forbidden; mutations add submitting/success and message delivery adds queued/sending/delivered/failed.
- Preserve form input and partial streamed text on recoverable failure.
- Workspace switching cancels pending requests and clears old scoped caches/drafts.
- Product/source cards render only server-validated evidence.
- Connection status comes from backend verification; unavailable providers never appear connected.
- Metrics state period/timezone and appear only when backed by persisted facts.
- Do not render raw provider HTML, private attachment URLs or unsanitized model output.

## Responsive and accessibility

Review at 1440, 1024, 768, 390 and 320 px. Multi-pane views become tabs or list-to-detail navigation on narrow screens. Chat composers respect safe areas and on-screen keyboards. Provide logical headings, labels/error associations, keyboard access, visible focus, focus restoration, 44 px primary touch targets, text status in addition to color and accessible chart/table alternatives. Streaming announcements are polite and throttled; reduced motion is respected.

## Reference images

Assets under `assets/reference/` guide visual language only: admin shell, agent workbench, Website widget and catalog density. Product/domain behavior and security rules always override screenshots.
