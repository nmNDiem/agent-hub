# World UI context router

Status: **APPROVED DIRECTION — not the current frontend implementation.**

The World is a coherent 2D overview of a workspace, its Agents, assignments, enabled capabilities, runtime state and attention areas. Product-wide principles in [`../../ui.md`](../../ui.md), domain ownership and the active phase override visual assumptions.

> Do not load every World file by default. Start from the active phase packet, then use the route matching the work.

## Product or information architecture

Required:

- [`WORLD_UI_SPEC.md`](WORLD_UI_SPEC.md)
- [`INFORMATION_RULES.md`](INFORMATION_RULES.md)

Add [`../../product.md`](../../product.md) only if the phase changes product scenarios or capability meaning.

## Visual design or visual semantics

Required:

- [`WORLD_UI_SPEC.md`](WORLD_UI_SPEC.md)
- [`VISUAL_GRAMMAR.md`](VISUAL_GRAMMAR.md)

Add [`INFORMATION_RULES.md`](INFORMATION_RULES.md) when changing information density/ownership. The reference image is mood/composition evidence only.

## Interaction behavior

Required:

- [`INTERACTION_SPEC.md`](INTERACTION_SPEC.md)

Add [`VISUAL_GRAMMAR.md`](VISUAL_GRAMMAR.md) only when interaction changes visual meaning; add [`WORLD_UI_SPEC.md`](WORLD_UI_SPEC.md) only when it changes projection/hierarchy.

## Renderer, canvas or layout implementation

Required:

- [`WORLD_TECH_SPEC.md`](WORLD_TECH_SPEC.md)
- [`INTERACTION_SPEC.md`](INTERACTION_SPEC.md)

Conditional:

- [`VISUAL_GRAMMAR.md`](VISUAL_GRAMMAR.md) — rendered symbols/levels change.
- [`INFORMATION_RULES.md`](INFORMATION_RULES.md) — aggregation or ownership changes.
- [`fixtures/world-demo.ts`](fixtures/world-demo.ts) — prototype fixture work.

Candidate dependencies in the technical specification are not installed or approved automatically. The phase must justify each addition.

## Review or acceptance

Required:

- [`ACCEPTANCE_CRITERIA.md`](ACCEPTANCE_CRITERIA.md)
- The active phase's acceptance criteria

Load only the specification implicated by a failed criterion. [`PROMPT_CODEX.md`](PROMPT_CODEX.md) is a handoff aid, not independent authority.

## Required scenarios

- Knowledge-only workspace: Agents, Knowledge, Channels and conversations without Commerce UI.
- Commerce-enabled workspace: the supplied fixture may demonstrate Catalog relationships.

Capabilities are contextual. Absence of Commerce removes its controls/nodes rather than producing empty placeholders. Conventional accessible navigation remains available; the spatial projection is not a second state model.

## Non-goals

The World is not a whiteboard, workflow builder, database graph, KPI wall, 3D/game scene or replacement for Inbox, forms, imports and record tables.
