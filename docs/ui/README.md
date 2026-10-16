# AgentHub World UI specification

Status: **APPROVED DIRECTION — not the current frontend implementation.**

This directory is the detailed context packet for a future World UI slice. Product-wide UI principles and delivery boundaries in [`../ui.md`](../ui.md) take precedence. Domain ownership in [`../domains/`](../domains/) and security rules also override visual assumptions.

The World is a coherent 2D overview for understanding a workspace, its agents, their assignments, enabled capabilities, runtime state, and areas needing attention. It is not a decorative graph, generic dashboard, or replacement for focused operational screens.

## Reading route for a World task

Read in this order:

1. [`../ui.md`](../ui.md) — product-wide rules and current/planned boundary.
2. [`WORLD_UI_SPEC.md`](WORLD_UI_SPEC.md) — product model, projections, hierarchy, and scope.
3. [`INFORMATION_RULES.md`](INFORMATION_RULES.md) — ownership, aggregation, and anti-clutter rules.
4. [`INTERACTION_SPEC.md`](INTERACTION_SPEC.md) — navigation, zoom, focus, selection, and inspector behavior.
5. [`VISUAL_GRAMMAR.md`](VISUAL_GRAMMAR.md) — stable visual meaning.
6. [`WORLD_TECH_SPEC.md`](WORLD_TECH_SPEC.md) — proposed renderer boundaries; dependencies still require task-level approval.
7. [`ACCEPTANCE_CRITERIA.md`](ACCEPTANCE_CRITERIA.md) — completion gate.
8. [`fixtures/world-demo.ts`](fixtures/world-demo.ts) — Commerce-enabled test fixture, not a universal workspace schema.

[`PROMPT_CODEX.md`](PROMPT_CODEX.md) is a handoff aid, not an independent authority. Reference images are visual mood/composition references only.

## Required scenarios

- A knowledge-only workspace with Agents, Knowledge, Channels, and conversations but no Commerce UI.
- A Commerce-enabled workspace using the supplied fixture.

Capabilities are contextual. Catalog, Inventory, Orders, or Customers projections must not appear merely because a fixture contains them. The current frontend dependencies do not include all packages proposed by the technical spec; an approved plan must justify additions before implementation.

## Priority order

1. Domain correctness and tenant safety.
2. Information architecture and ownership/no duplication.
3. Interaction clarity and accessibility.
4. Visual hierarchy and performance.
5. Animation and decoration.

The World is not a whiteboard, workflow builder, database graph, KPI wall, 3D/game scene, or substitute for Inbox, forms, imports, and record tables.
