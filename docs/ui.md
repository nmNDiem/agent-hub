# Product UI principles

This is the product-wide UI authority. [`ui/`](ui/) contains the approved **World** concept and implementation-ready design details; it does not describe the current frontend unless explicitly marked.

## Current implementation

The dashboard is a Vietnamese, route-based SaaS control panel for Overview, Inbox, Contacts, Agents, Catalog, Knowledge, Channels, Analytics, and Settings. The agent workbench combines configuration, Playground, publishing, and channel assignment. Website, Facebook, and Zalo share the implemented inbox/contact operations.

Current navigation reflects the shipped Commerce-first product. It must remain compatible until a task delivers capability-aware navigation and equivalent access to existing behavior.

## Approved direction

AgentHub should feel like an operational environment, not a database administration panel or generic CMS. Users should understand their workspace, agents, knowledge, channels, and enabled domain capabilities before encountering records and settings.

The **World** is the preferred spatial overview: agents and capability areas form a navigable map, while focused work still uses legible lists, forms, tables, and inspectors. Spatial presentation is a projection of real backend state, never a second state model.

Principles:

- Establish clear hierarchy: workspace context, operational state, next action, then detail.
- Reveal configuration progressively; do not place every field and action on one screen.
- Show a concept once in its clearest location and link to it elsewhere rather than duplicating panels.
- Make navigation contextual. A workspace without Commerce must not see empty Catalog, Inventory, or Orders areas as if they were core requirements.
- Keep capability states honest: unavailable, disconnected, empty, degraded, and unauthorized are distinct.
- Use real persisted data. Never fabricate products, people, dates, IDs, metrics, delivery state, or provider health.
- Avoid “AI slop”: decorative gradients, excessive cards, meaningless activity, faux intelligence, and motion without information.
- Preserve user input and partial streamed output on recoverable errors.

## Interaction and accessibility

Every async surface supports loading, ready, empty, error, and forbidden states; mutations also communicate submission and success, while deliveries expose their real lifecycle. Workspace changes cancel pending requests and clear tenant-scoped caches and drafts.

The UI must provide semantic structure, keyboard access, visible focus, associated labels/errors, text in addition to color, reduced-motion behavior, and accessible alternatives for charts or spatial views. Test responsive behavior at 1440, 1024, 768, 390, and 320 pixels. Dense multi-pane tools become tabs or list-to-detail navigation on narrow screens.

Product/source cards render only server-validated evidence. Connection status comes from backend verification. Raw provider HTML, private attachment URLs, unsanitized model output, and secrets never render.

## World delivery boundary

The World documents are an approved target specification. PixiJS, ELK, d3-force, Motion, or similar packages are not assumed to exist in the current app and must not be added until an approved implementation slice justifies them. A first slice must preserve conventional accessible navigation and prove both a knowledge-only workspace and a Commerce-enabled workspace.

## Visual language

Use the shared design tokens in [`ui-tokens.json`](ui-tokens.json). Workspace/widget branding remains bounded by accessibility and security rules. Reference assets guide visual language only; product, domain, and security rules override screenshots and fixtures.
