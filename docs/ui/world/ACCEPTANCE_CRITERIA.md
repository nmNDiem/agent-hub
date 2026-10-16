# AgentHub World — Acceptance Criteria

Status: **APPROVED DIRECTION.** These criteria apply to an approved World implementation task; they do not describe current product behavior.

The first World prototype is accepted only when all mandatory criteria below are met.

## 1. Information architecture

- [ ] Default screen communicates workspace structure without requiring a KPI dashboard.
- [ ] Every visible object belongs to the documented domain grammar.
- [ ] Every visible edge has a meaningful relationship defined in the current projection.
- [ ] The screen has one clear primary question.
- [ ] The same fact is not duplicated across canvas, toolbar and inspector.
- [ ] Healthy state remains visually quiet.
- [ ] Exceptional state receives stronger emphasis than normal state.

## 2. Structural model

Using `fixtures/world-demo.ts` as the Commerce-enabled scenario:

- [ ] Sales Agent is shown as a primary cluster anchor.
- [ ] Website, Facebook and Zalo are shown as channel gateways connected to Sales Agent.
- [ ] Product Knowledge and Policy Knowledge are shown as knowledge assigned to Sales Agent.
- [ ] Catalog scope exposes Women collection and HCM Q1 / HCM Q7 locations at the appropriate semantic level.
- [ ] Support Agent exists as a second cluster and remains spatially distinguishable.
- [ ] Conversation activity is aggregated; 184 actual conversation nodes are not rendered.
- [ ] A knowledge-only scenario renders coherently with no Catalog, Inventory, Orders or Customers controls/nodes.
- [ ] An absent capability leaves no empty projection or placeholder.

## 3. Navigation and projections

- [ ] Global navigation does not duplicate World projections as redundant routes.
- [ ] World includes relevant core projections; Catalog and Customers controls appear only when their capabilities exist.
- [ ] System is the default projection.
- [ ] Switching projections changes visibility/emphasis, not just color.
- [ ] Projection switching preserves context where practical.

## 4. Pan, zoom and semantic zoom

- [ ] Canvas pans smoothly.
- [ ] Canvas zooms smoothly.
- [ ] Minimum and maximum zoom are bounded.
- [ ] Semantic Level A hides secondary detail.
- [ ] Semantic Level B shows primary structure.
- [ ] Semantic Level C reveals agent composition.
- [ ] Zooming does not merely scale all labels and objects uniformly.

## 5. Selection and focus

- [ ] Selecting an agent emphasizes only meaningful direct relationships.
- [ ] Selection does not globally scramble the layout.
- [ ] Selecting an object opens a contextual DOM inspector when appropriate.
- [ ] Clicking empty canvas clears selection.
- [ ] Focusing an agent animates camera toward its cluster.
- [ ] Escape/back returns to prior context.

## 6. Inspector

- [ ] Inspector is React DOM, not rendered inside Pixi.
- [ ] Inspector does not repeat facts already owned by the canvas unless decomposing them.
- [ ] Inspector does not contain empty generic sections.
- [ ] Agent inspector exposes runtime breakdown only when agent is selected.
- [ ] Configuration actions are placed in inspector/detail surface, not floating randomly on canvas.

## 7. Visual grammar

- [ ] Agent, knowledge, channel, catalog, collection and location are visually distinguishable by stable grammar.
- [ ] Shapes/icons are reused consistently across the product.
- [ ] No employee avatar representation for agents.
- [ ] No 3D perspective.
- [ ] No rotate/flip effects.
- [ ] No card wall.
- [ ] No permanent rainbow/neon treatment on every node/edge.

## 8. Activity

- [ ] Runtime activity is represented as aggregate state and/or capped particles.
- [ ] Ambient activity can be disabled via reduced motion.
- [ ] Activity effects do not obscure structural relationships.
- [ ] One degraded/error example is visible and clearly tied to the affected object.

## 9. Performance

- [ ] No force simulation runs continuously after layout settles.
- [ ] Camera movement does not trigger full React application re-render.
- [ ] Prototype remains smooth with the canonical fixture.
- [ ] Layout positions are cached/stabilized.

## 10. Accessibility

- [ ] Projection controls are native DOM controls.
- [ ] Inspector is keyboard reachable.
- [ ] Selected object identity/state is exposed accessibly.
- [ ] Essential state is not conveyed by color alone.
- [ ] `prefers-reduced-motion` is honored.

## 11. Anti-slop gate

Before merge, reviewer must confirm all statements:

- [ ] Every visible object has a clear product reason to exist.
- [ ] Every visible edge has a clear relationship reason to exist.
- [ ] No removable repeated metric remains on the screen.
- [ ] No element exists only to make the UI look more professional.
- [ ] No decorative animation remains when removing it would improve clarity.
- [ ] The canvas still makes sense when all ambient animation is disabled.
- [ ] The page remains understandable without reading the inspector first.

Any unchecked item fails the UI review.
