# AgentHub World UI Specification

Status: **APPROVED DIRECTION — not the current frontend implementation.** Product-wide UI authority and delivery boundaries live in [`../../ui.md`](../../ui.md).

## 1. Purpose

AgentHub contains several domains that already relate to each other: agents, knowledge, channels, catalog scope, locations, conversations, contacts, handoff and operational state.

The World UI must expose those relationships in a structured 2D model so a user can answer:

> What is this workspace made of, how are the important parts connected, and where does attention belong?

It must not try to show every record or metric at once.

---

## 2. Core domain model

The default structural model below is a Commerce-enabled example. In the general model, domain capability branches are optional and appear only when enabled:

```text
Workspace
├── Agents
│   ├── Knowledge assignments
│   ├── Channel connections
│   └── Catalog scope
│       ├── Collections
│       └── Locations
│
└── Runtime activity
    ├── Conversations
    ├── Contacts / leads
    └── Human handoff
```

The World must represent the **meaningful product relationships**, not the physical database schema. The Commerce-heavy fixture demonstrates one workspace; it is not the universal product model. A knowledge-only workspace omits Catalog scope and its descendants without leaving empty controls.

### Structural relationships that may be visible

```text
Channel -> Agent
Knowledge -> Agent
Agent -> Catalog scope
Catalog scope -> Collection
Catalog scope -> Location
Agent -> Aggregated activity
```

### Relationships that must not be rendered as persistent graph edges by default

```text
Conversation -> Contact
Contact -> Tag
Contact -> Assignee
Contact -> Lead
Message -> Conversation
Chunk -> Knowledge source
Product -> Variant
Variant -> Inventory row
```

Those relationships belong in lower-detail views, inspectors, drill-downs or dedicated operational screens.

---

## 3. Primary projections

The World has multiple projections over the same underlying workspace model. A projection changes emphasis, aggregation and visibility. It does not create a separate application.

### 3.1 System projection

Primary question:

> How is this workspace structurally connected?

Show:

- agents
- channels connected to each agent
- knowledge assigned to each agent
- catalog scope assigned to each agent
- compact aggregated activity state
- exceptions requiring attention

Do not show:

- charts
- long activity lists
- per-contact nodes
- per-conversation nodes
- token usage
- detailed analytics
- repeated counts in multiple regions

This is the default projection.

### 3.2 Agents projection

Primary question:

> How are agents configured and how do their scopes differ?

Emphasize:

- agent boundaries
- assigned knowledge
- connected channels
- collection/location scope
- publish/paused/attention state

De-emphasize:

- customer population
- catalog inventory details
- broad analytics

### 3.3 Catalog projection

Primary question:

> How does catalog scope relate to collections, locations and agents?

Emphasize:

```text
Agent
  -> Catalog scope
      -> Collections
      -> Locations
```

At deeper zoom, a selected collection or location may reveal aggregate product or stock information, but not full product tables on the canvas.

### 3.4 Customers projection

Primary question:

> Where is customer/conversation activity flowing, and which agents or channels are carrying it?

Emphasize:

- aggregated activity
- channel origin
- agent handling
- AI vs human state
- pending/attention conditions

Do not render every contact as a persistent node.

### 3.5 Health projection

Health is an overlay, not a separate dashboard.

Primary question:

> Which structural component requires attention?

Normal healthy state should remain visually quiet. Only degraded, disconnected, expired or failed states gain emphasis.

---

## 4. Spatial hierarchy

The canvas must have a stable conceptual order.

### Default System projection

Use this directional grammar when possible:

```text
External entry      Intelligence          Business scope / outcome

Channels       ->       Agent       <-       Knowledge
                         |
                         v
                    Catalog scope
                         |
                 Collections / Locations

Runtime activity is attached to the agent as aggregate state,
not spread randomly around the canvas.
```

This is a semantic rule, not a rigid coordinate system. Layout may adapt to available space, multiple agents and responsive size.

### Multi-agent workspace

For multiple agents:

- each agent is a primary cluster anchor
- shared resources may sit between relevant agents only when that relation is useful
- avoid edge crossings where possible
- avoid duplicating the same shared resource node solely to make layout easier
- if a resource is shared by many agents, aggregate or use a shared hub representation

The user should be able to understand cluster boundaries at a glance.

---

## 5. Levels of detail / semantic zoom

Zoom must change information density. It must not merely scale graphics.

### Level A — Workspace topology

Approximate intent: zoomed out.

Show:

- agent identity
- agent state
- major connected domain groups
- attention markers

Hide:

- minor labels
- individual knowledge sources
- individual locations
- detailed activity state

Example:

```text
◉ Sales        ◉ Support        ◉ CSKH
```

### Level B — Structural relationships

Default working zoom.

Show:

```text
Website -> Sales Agent <- Product Knowledge
                   |
                Catalog
```

Also show compact aggregate runtime state if relevant.

### Level C — Composition

Focused/zoomed-in agent.

Reveal:

- assigned knowledge items
- connected channels
- catalog collections/locations
- state decomposition

Do not automatically open record tables.

### Level D — Detail

Detail belongs primarily in React DOM inspector or dedicated screens.

Examples:

- source records
- location inventory table
- conversation list
- configuration form
- publish settings

The canvas should not become a CRUD surface.

---

## 6. Selection and focus

There are three visual states:

### Neutral

No object selected. The canvas shows the current projection with low-noise hierarchy.

### Selected

A single object is selected. Its direct meaningful relationships are emphasized. Unrelated content is reduced in prominence but remains spatially stable.

### Focused

The user explicitly focuses an object or cluster. Camera moves to that object and semantic zoom reveals the next level of composition.

Selection must not arbitrarily re-layout the entire world.

---

## 7. Inspector ownership

The inspector exists for information or actions that should not live on the canvas.

The inspector must **decompose** a selected object rather than duplicate the exact same facts already shown on the canvas.

Example:

If the canvas owns:

```text
Sales Agent — 184 active conversations
```

then the inspector may own:

```text
AI handling      132
Human handling    21
Waiting           28
Failed             3
```

but should not repeat a separate heading whose only purpose is to say `184` again.

Inspector sections should be conditional. Empty or irrelevant sections must not be rendered just to preserve a template.

---

## 8. Runtime activity model

Conversations are activity, not permanent structural nodes.

Default representation:

- aggregate count
- subtle flow/particle activity
- compact state breakdown when focused
- warning marker when failures or pending state need attention

Do not create one canvas object for each conversation in normal operation.

Contact/customer activity should be represented as an aggregate population or flow until the user explicitly drills down.

---

## 9. Normal vs exceptional state

Default healthy state:

- quiet
- low contrast secondary edges
- subtle or no animation
- no green badge repeated everywhere

Exceptional state:

- stronger visual priority
- concise reason
- direct relationship to affected object

Examples:

```text
Facebook connection
! Reauthorization required
```

```text
Knowledge source
! Stale / failed ingestion
```

```text
Agent
! Paused
```

A healthy application should visually calm down rather than glow more.

---

## 10. Navigation model

Keep global navigation minimal.

Recommended top-level product navigation:

```text
World
Inbox
Settings
```

Within World, use projection controls:

```text
System | Agents | Catalog | Customers
```

Do not duplicate projections as both persistent sidebar routes and World tabs unless product requirements later prove the need.

Inbox remains a dedicated operational surface because high-volume conversation work is better handled as a list/detail interface.

Settings remains a dedicated configuration surface.

---

## 11. Empty states

Empty state must preserve the spatial model.

Example: no agent exists.

Do not show an empty KPI dashboard.

Show a clear World canvas with one meaningful primary action:

```text
Create your first agent
```

Once the agent exists, reveal its available structural attachment points progressively.

---

## 12. Responsive behavior

Desktop is the primary World experience.

### Large desktop

- canvas occupies majority of viewport
- inspector may dock right
- minimap optional when world exceeds one viewport

### Medium width

- inspector overlays or collapses
- canvas remains primary
- labels reduce according to semantic priority

### Mobile

Do not shrink the full desktop graph into unreadability.

Prefer:

- focused cluster view
- list-to-focus navigation
- full-screen inspector transitions
- simplified projection controls

Mobile must retain the same domain grammar even if spatial overview is reduced.

---

## 13. Out of scope for the first prototype

Do not implement in the first vertical prototype:

- all production data integration
- free-form user dragging of structural nodes
- saved manual layouts
- full analytics overlays
- per-product visualization
- per-contact visualization
- graph editing
- collaboration cursors
- custom themes
- onboarding walkthrough

First prove the spatial model and interaction quality.
