# Prompt for Codex — AgentHub World Prototype

Use this prompt after placing this `docs/ui/` directory into the AgentHub repository.

---

Read `AGENTS.md` and every file under `docs/ui/` before proposing changes.

Treat `docs/ui.md` as product-wide authority and `docs/ui/` as the approved target specification for the AgentHub World interface. Do not treat it as evidence of current implementation.

The written specifications override the reference image whenever they conflict.

Your task is to implement one coherent vertical prototype of the AgentHub World using the current frontend architecture and the canonical fixture in `docs/ui/fixtures/world-demo.ts`.

Scope of this implementation:

- World / System projection
- stable pan and zoom
- semantic zoom with distinct levels of detail
- structural Agent / Channel / Knowledge / Catalog relationships
- agent selection
- agent focus
- contextual React DOM inspector
- aggregate runtime activity
- one clear attention/error state
- projection controls prepared for System / Agents and only enabled domain capabilities

Candidate architecture to validate in the plan (do not install dependencies before approval):

- Next.js / React for application UI
- PixiJS for the 2D World renderer
- ELK for structural/hierarchical layout where appropriate
- d3-force only for small organic/local layouts where appropriate
- Motion for React DOM transitions where useful
- normal React DOM for inspector, controls, forms and accessible interaction surfaces

Do not use:

- Three.js
- 3D or fake perspective
- React Flow as the World renderer
- tldraw as the World renderer
- free-form draggable graph editing
- rotating/flipping UI
- generic KPI dashboard cards
- decorative nodes or edges without domain meaning
- repeated metrics on the same screen
- continuous force-directed motion

Information rules are mandatory:

- one screen/projection answers one primary question
- one fact has one visual owner
- normal state is visually quiet
- exceptional state receives emphasis
- aggregate large collections before visualizing individual records
- do not render every database relationship as an edge
- detail appears progressively through semantic zoom or explicit selection
- do not add controls, labels, badges, charts, cards, animation or metadata merely to make the interface look more complete

Before writing code, audit the existing frontend and return a concrete implementation plan containing:

1. existing files/components that can be reused
2. files to add/change
3. World domain/render model
4. Pixi/React ownership boundary
5. layout strategy and why each layout engine is used
6. semantic zoom levels
7. selection/focus state flow
8. inspector information ownership
9. performance risks
10. accessibility approach
11. tests to add

The plan must be internally coherent with all files under `docs/ui/`, prove a knowledge-only workspace as well as the Commerce fixture, and follow the repository rule that implementation starts only after plan approval.

Do not redesign the information architecture.
Do not expand scope beyond the first vertical prototype.
Do not add "professional-looking" filler.

After planning, implement against the canonical fixture first. Production data wiring can follow only after the interaction model is coherent.

Use `docs/ui/ACCEPTANCE_CRITERIA.md` as the completion gate.
