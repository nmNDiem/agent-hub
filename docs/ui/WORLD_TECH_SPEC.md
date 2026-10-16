# AgentHub World — Technical Specification

Status: **PROPOSED IMPLEMENTATION FOR AN APPROVED UI DIRECTION.** The current web package does not include every rendering/layout dependency named below. An approved World task must audit the frontend, justify each dependency, and receive plan approval before adding it.

## 1. Candidate stack

Use the existing Next.js / React application shell.

Proposed World stack (subject to task approval):

```text
Next.js / React
|
├── React DOM
│   ├── app shell
│   ├── projection controls
│   ├── inspector
│   ├── forms / dialogs
│   └── accessible interaction surface
│
├── PixiJS
│   └── 2D World renderer
│
├── d3-force
│   └── organic/local cluster layout where appropriate
│
├── ELK
│   └── layered / structural layout where appropriate
│
└── Motion
    └── DOM panel/layout transitions
```

Do not install every candidate by default. Prefer a deterministic DOM/CSS solution when it satisfies the accepted slice. If a canvas is justified, use `@pixi/react` only if its integration is clean with the current React version and project architecture; direct PixiJS is acceptable when it creates a clearer ownership boundary. Use ELK, d3-force, or Motion only for a demonstrated need.

---

## 2. Renderer responsibility

### PixiJS owns

- world background
- structural nodes
- structural edges
- aggregate runtime particles
- canvas labels where appropriate
- hit regions for canvas interactions
- camera transform
- selection/focus emphasis inside the canvas

### React DOM owns

- global navigation
- projection controls
- inspector
- tooltips that require rich content
- menus
- forms
- dialogs
- accessibility mirror/navigation
- dedicated record/detail UI

Do not implement the inspector inside Pixi.

---

## 3. Layout architecture

Do not choose one layout engine for every projection.

Recommended:

```text
Domain graph
  |
  ├── projection adapter
  |     -> decides visible objects/relations
  |
  ├── layout strategy
  |     ├── ELK layered layout
  |     ├── D3 local/organic layout
  |     └── custom deterministic layout
  |
  └── render model
        -> PixiJS scene
```

### ELK

Use for:

- explicit hierarchy
- channel -> agent -> business scope arrangement
- multi-agent structural topology
- cases where crossing reduction matters

### D3-force

Use for:

- small organic clusters
- customer/activity cloud
- local separation/collision

Run simulations to settle; do not leave the whole interface perpetually floating.

### Custom deterministic layout

Prefer custom layout when the domain has a simple known arrangement. Do not invoke a heavy layout engine merely because it exists.

---

## 4. Domain model vs render model

Do not pass backend objects directly into Pixi components.

Define an intermediate World model.

Example:

```ts
export type WorldNodeKind =
  | "agent"
  | "knowledge"
  | "channel"
  | "catalog"
  | "collection"
  | "location"
  | "activity";

export interface WorldNode {
  id: string;
  kind: WorldNodeKind;
  label: string;
  state: "normal" | "active" | "processing" | "attention" | "error" | "paused";
  parentId?: string;
  importance: 1 | 2 | 3;
  metadata?: Record<string, unknown>;
}

export interface WorldEdge {
  id: string;
  source: string;
  target: string;
  kind: "structural" | "channel" | "runtime" | "attention";
}
```

Projection adapters decide what is visible at each semantic level.

---

## 5. Suggested module boundaries

Exact paths may adapt to the current repository, but responsibilities should remain separated.

```text
features/world/
├── world-page.tsx
├── world-shell.tsx
├── world-store.ts
│
├── model/
│   ├── world-types.ts
│   ├── build-world-model.ts
│   └── projections.ts
│
├── layout/
│   ├── layout-types.ts
│   ├── system-layout.ts
│   ├── elk-layout.ts
│   ├── force-layout.ts
│   └── layout-cache.ts
│
├── canvas/
│   ├── world-stage.tsx
│   ├── camera-controller.ts
│   ├── semantic-zoom.ts
│   ├── nodes/
│   ├── edges/
│   └── activity/
│
├── inspector/
│   ├── world-inspector.tsx
│   └── inspectors/
│
└── fixtures/
```

Avoid a single 2,000-line World component.

---

## 6. State ownership

Keep state categories separate.

### Domain state

Fetched workspace data.

### Projection state

```text
system | agents | catalog | customers
```

### Camera state

- x
- y
- zoom
- focus target

### Selection state

- selected object ID
- focus history

### Layout state

- resolved positions
- cached stable positions

### UI state

- inspector open/closed
- contextual menu

Do not put all state into Pixi display objects.

---

## 7. Performance constraints

The first prototype should already avoid patterns that fail at scale.

Rules:

- do not create DOM node per world object inside the canvas
- aggregate conversation/contact activity
- cap particles
- cache layout results
- avoid running force simulation every frame
- avoid React re-render of the entire Pixi scene on camera movement
- use object pooling for frequently created activity particles if needed
- suspend ambient work when document hidden

Prototype target should remain smooth with at least:

```text
3 agents
10 channels/resources combined
10-20 structural child nodes
100+ logical conversation events represented through aggregation
```

No requirement to render 100 actual conversation nodes.

---

## 8. Accessibility

Pixi canvas is not sufficient by itself.

Provide an accessible DOM representation of the current structural model for keyboard/screen-reader navigation.

At minimum:

- selected object name/state available to assistive technology
- projection controls are native DOM controls
- inspector is standard DOM
- actions are reachable without pointer precision
- color is not the only state indicator

---

## 9. Styling

Use existing AgentHub design tokens where available.

If a new World token layer is needed, define semantic tokens, for example:

```text
world-bg
world-surface
world-text-primary
world-text-secondary
world-edge-structural
world-edge-muted
world-focus
world-attention
world-error
```

Do not hard-code a separate arbitrary color palette per node type throughout components.

---

## 10. Explicitly forbidden implementation choices

For the World renderer:

- no Three.js
- no 3D scene
- no WebGL 3D camera
- no fake perspective
- no rotating/flipping cards
- no React Flow as the core renderer
- no tldraw as the core renderer
- no free-form graph editor behavior
- no dashboard KPI card grid as the primary World
- no force-directed graph running continuously
- no visualization of every database relation

---

## 11. First vertical prototype

Implement only enough to prove the core system:

```text
System projection
+ fixture data
+ stable pan/zoom
+ semantic zoom
+ select agent
+ focus agent
+ contextual inspector
+ structural relationships
+ aggregate activity
+ one attention/error state
```

Do not begin with production data wiring if it slows validation of the interaction model. Use the canonical fixture first.

---

## 12. Tests

Minimum automated coverage:

### Model tests

- correct visible nodes for projection
- no duplicate IDs
- correct relationship construction
- aggregate values derived correctly

### Information ownership tests where practical

- total activity is not rendered in multiple owners in the same state
- hidden detail remains hidden at lower semantic levels

### Interaction tests

- select opens correct inspector
- clear selection closes contextual detail
- projection changes visible model
- focus changes semantic level

### Layout tests

Prefer invariant tests rather than pixel snapshots:

- no NaN positions
- major nodes receive positions
- child nodes remain within expected cluster proximity

Avoid brittle full-canvas screenshot tests as the only regression mechanism.
