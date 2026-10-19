# Product UI principles

Load this authority for user-visible behavior, interaction or accessibility changes. This is not routine backend context. [`ui/world/`](ui/world/) contains the approved **World** concept and routes work to only the required detailed specifications; it does not describe the current frontend unless explicitly marked.

## Current implementation

The dashboard is a Vietnamese, route-based SaaS control panel for Overview, Inbox, Contacts, Agents, Catalog, Knowledge, Channels, Analytics, and Settings. The agent workbench combines configuration, Playground, publishing, and channel assignment. Website, Facebook, and Zalo share the implemented inbox/contact operations.

Knowledge management distinguishes advisory freshness from ingestion health and the latest candidate from the active searchable version. Progressive document details expose metadata history, review, replacement and eligible recovery. The owner/admin diagnostic panel renders bounded validated snippets and textual zero/degraded reason codes; it does not use color or similarity score as a universal quality grade.

Agent workbench and Website preview copy is domain-neutral. It presents Knowledge or Catalog as alternative data sources and does not imply that a Knowledge-only Agent is a shopping assistant.

The workspace entry is an Agent-centric World that is the full system interface, not a tab inside a dashboard shell. It uses a static responsive DOM grid whose Agent count per row follows the available viewport, with selection/focus and an overlay inspector. A compact system header and capability-aware launcher replace the persistent sidebar: Catalog, Locations and Collections appear only when Commerce data exists, while authorized operators can reach an explicit optional Commerce setup action. Existing focused routes remain compatible—even where historical route identifiers still say `chatbots`—and open as contextual work views within the same route-level system boundary.

## Approved direction

AgentHub should feel like an operational environment, not a database administration panel or generic CMS. Users should understand their workspace, agents, knowledge, channels, and enabled domain capabilities before encountering records and settings.

The **World** is the workspace system surface: agents and their enabled capabilities are visible together in a responsive, document-flow layout, while focused work uses legible lists, forms, tables, and inspectors. The presentation is a projection of real backend state, never a second state model or a draggable canvas.

Phase 3.2 establishes the product interaction language rather than merely reskinning pages. A workspace overview should show multiple Agents and their real relationships to Knowledge, Channels, Conversations, handover/attention state and enabled domain systems. Selecting an Agent leads coherently through:

```text
Create -> Configure -> Give Knowledge -> Grant abilities/domain access
       -> Test -> Publish -> Observe -> Improve
```

An Agent is represented as an identifiable operational actor, not only a prompt/model form. The overview is not a substitute for Agent, Knowledge, Inbox or domain detail screens; those remain the focused places for deep work.

Principles:

- Establish clear hierarchy: workspace context, operational state, next action, then detail.
- Reveal configuration progressively; do not place every field and action on one screen.
- Show a concept once in its clearest location and link to it elsewhere rather than duplicating panels.
- Make navigation contextual. A workspace without Commerce must not see empty Catalog, Inventory, or Orders areas as if they were core requirements.
- Keep capability states honest: unavailable, disconnected, empty, degraded, and unauthorized are distinct.
- Use real persisted data. Never fabricate products, people, dates, IDs, metrics, delivery state, or provider health.
- Avoid “AI slop”: decorative gradients, excessive cards, meaningless activity, faux intelligence, and motion without information.
- Preserve user input and partial streamed output on recoverable errors.
- Present capabilities in user language such as “can schedule an appointment”; do not require users to understand form engines, function schemas or capability registries.
- Keep one visual owner for each fact. A relationship, count or status already clear in the World is linked rather than repeated in a filler card on the same view.
- Make publish meaningful: expose real draft/published/paused state and derived blocking readiness facts without inventing completion or connection state.
- Provide minimum guidance now through useful empty states, next-step suggestions, inline explanations, validation and actionable errors. Full guided onboarding remains a later phase.

## Interaction and accessibility

Every async surface supports loading, ready, empty, error, and forbidden states; mutations also communicate submission and success, while deliveries expose their real lifecycle. Workspace changes cancel pending requests and clear tenant-scoped caches and drafts.

The UI must provide semantic structure, keyboard access, visible focus, associated labels/errors, text in addition to color, reduced-motion behavior, and accessible alternatives for charts or spatial views. Test responsive behavior at 1440, 1024, 768, 390, and 320 pixels. Dense multi-pane tools become tabs or list-to-detail navigation on narrow screens.

Product/source cards render only server-validated evidence. Connection status comes from backend verification. Raw provider HTML, private attachment URLs, unsanitized model output, and secrets never render.

## World delivery boundary

The World documents route design work to the active approved implementation packet. The current system-first interface deliberately uses semantic HTML and CSS Grid; it does not use Canvas/WebGL, authored graph coordinates, pan/zoom controls or a separate mobile rendering model. A single responsive DOM hierarchy must preserve conventional accessible navigation and support both Knowledge-only and Commerce-enabled workspaces.

The World must not imitate a 3D game, rotate/flip cards, add decorative floating panels or use generic AI-person imagery. Motion communicates selection, focus, activity or state change and respects reduced motion.

## Visual language

Use the shared design tokens in [`ui-tokens.json`](ui-tokens.json). Workspace/widget branding remains bounded by accessibility and security rules. Reference assets guide visual language only; product, domain, and security rules override screenshots and fixtures.
