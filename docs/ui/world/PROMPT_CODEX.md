# World prototype handoff

Use this only from an explicitly approved World phase packet. It is a reusable handoff aid, not scope authority.

1. Read `AGENTS.md`, the active phase and [`README.md`](README.md).
2. Follow the router for the assigned concern; do not read every World document automatically.
3. Inspect the current frontend and return the required plan before implementation.

For a first coherent System-projection prototype, the phase may include stable pan/zoom, semantic zoom, Agent/Channel/Knowledge and contextual optional-Catalog relationships, selection/focus, a React DOM inspector, aggregated runtime activity, one attention state and capability-aware projection controls.

Candidate architecture—validate rather than assume:

- existing Next.js/React shell;
- React DOM for controls, inspector, forms and accessible navigation;
- PixiJS only when canvas rendering is justified;
- ELK only for demonstrated structural layout needs;
- d3-force only for small settled organic/local layouts;
- Motion only for useful DOM transitions.

Do not install dependencies before plan approval. Do not use Three.js, fake 3D, React Flow/tldraw as the World renderer, free-form graph editing, rotation/flip effects, KPI-card filler, decorative relationships, repeated metrics or continuous force motion.

The plan must cover reused components, files changed, domain/render model, renderer/DOM ownership, layout strategy, semantic zoom, selection/focus state, inspector information ownership, performance, accessibility and tests. It must preserve both the knowledge-only scenario and the Commerce fixture.

Implement against [`fixtures/world-demo.ts`](fixtures/world-demo.ts) only when the approved phase says to. Use [`ACCEPTANCE_CRITERIA.md`](ACCEPTANCE_CRITERIA.md) as the review gate and load the specific supporting spec only when a criterion requires it.
