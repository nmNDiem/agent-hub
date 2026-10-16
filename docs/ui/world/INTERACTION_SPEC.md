# AgentHub World — Interaction Specification

## 1. Interaction model

The World supports exploration, not free-form editing.

Core interactions:

- pan
- zoom
- select
- focus
- change projection
- open contextual inspector
- drill down into dedicated operational/detail screens

Structural nodes should not be freely draggable by default.

---

## 2. Camera

### Pan

- drag empty canvas
- trackpad pan supported
- avoid accidental panning when interacting with DOM overlays

### Zoom

- wheel / trackpad zoom centered around pointer where practical
- zoom controls optional as secondary affordance
- clamp minimum and maximum zoom
- zoom transitions should be smooth but not sluggish

### Fit

Provide a `fit world` action when the spatial graph is larger than viewport.

A minimap is optional and should appear only when the world exceeds one screen enough to justify it.

---

## 3. Semantic zoom transitions

Crossing semantic thresholds should change representation without abrupt re-layout.

Example:

### Level A -> Level B

Reveal:

- major edges
- domain labels
- compact activity aggregate

### Level B -> Level C

Reveal:

- individual knowledge assignments
- connected channel labels
- collections/locations under catalog scope

Hidden content should fade/resolve cleanly. Avoid dozens of elements popping simultaneously.

---

## 4. Selection

Single click/tap selects one object.

Selection behavior:

- preserve current camera position
- visually emphasize selected object
- emphasize direct meaningful relations
- reduce unrelated visual noise
- open inspector when the object has contextual information/actions

Clicking empty canvas clears selection.

Selection should not trigger a full graph re-layout.

---

## 5. Focus

Focus is stronger than selection.

Trigger:

- double click
- Enter on selected object
- explicit `Focus` action in inspector

Focus behavior:

- animate camera toward target cluster
- move to appropriate semantic zoom level
- reveal relevant child structure
- preserve enough surrounding context to retain orientation

Escape / back returns to previous focus context.

Maintain a small focus history stack.

---

## 6. Projection switching

Projection controls change what the World prioritizes.

Initial controls:

```text
System | Agents | Catalog | Customers
```

Rules:

- preserve selected object where valid
- preserve approximate camera context where possible
- animate only necessary transitions
- do not reconstruct the entire application shell
- do not duplicate the projection as separate sidebar navigation

---

## 7. Hover

Hover may provide lightweight affordance:

- hit target feedback
- relationship emphasis
- short tooltip only when label/detail is otherwise hidden

Do not rely on hover for essential information.

Avoid rich floating cards for every hovered object.

---

## 8. Inspector

Desktop inspector behavior:

- docks right when selected object warrants it
- does not cover the selected object when avoidable
- width stable within a small number of modes

Inspector content order:

```text
Identity
-> exceptional state if any
-> composition/details not already owned by canvas
-> actions
```

Do not default to generic tabs such as `Overview / Activity / Configuration` unless actual content density justifies them.

Prefer one contextual scroll surface first.

---

## 9. Dedicated screen handoff

World should hand off to dedicated screens when the task becomes record-heavy.

Examples:

- `View conversations` -> Inbox with context/filter
- `Manage knowledge` -> knowledge management detail
- `Manage catalog` -> catalog management detail
- `Edit agent` -> agent configuration surface

Return navigation should preserve World projection/focus where practical.

---

## 10. Activity animation

Activity animation is optional and restrained.

Use when it helps explain flow:

```text
Channel -> Agent -> runtime activity
```

Rules:

- aggregate rather than one animation per real event at scale
- cap particle count
- do not animate every structural edge
- pause/reduce when tab not visible
- honor `prefers-reduced-motion`

---

## 11. Layout stability

Stable spatial memory is critical.

When data changes:

- existing major nodes should remain near their established positions
- new child nodes should emerge near parent
- removal should close local space without globally reshuffling everything

D3/ELK output should be constrained by layout persistence, not blindly recomputed every render.

---

## 12. Keyboard

Minimum desktop keyboard behavior:

- `Tab` reaches projection controls and inspector actions
- arrow navigation between nearby canvas objects where feasible
- `Enter` selects/focuses
- `Escape` clears inspector or steps back focus
- `/` or command palette shortcut may open global search later

Canvas-only objects must have accessible DOM counterparts or an equivalent accessible navigation model.

---

## 13. Reduced motion

With reduced motion enabled:

- disable ambient particles
- replace camera easing with short/simple transitions
- no pulsing loops
- maintain state changes through opacity/stroke/label rather than motion alone

---

## 14. Loading

Avoid skeleton cards over the canvas.

Preferred behavior:

- shell loads first
- world viewport appears
- structure resolves progressively
- local loading state belongs to affected object/cluster

Do not block the whole World for a secondary data fetch if primary structure is already known.
