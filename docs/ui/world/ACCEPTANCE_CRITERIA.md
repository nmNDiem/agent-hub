# AgentHub World — Acceptance Criteria

Status: **CURRENT — aligned with Phase 3.2.1 system-first workspace interface.**

These criteria apply to the static responsive World delivered by Phase 3.2.1. They supersede the earlier canvas prototype criteria for projections, pan, zoom, camera focus and semantic zoom.

## 1. Information architecture

- [x] The default screen communicates workspace structure without requiring a KPI dashboard.
- [x] Every visible object belongs to the documented domain grammar and every visible relationship has a product meaning.
- [x] The same fact is not duplicated across World, the system header and the inspector.
- [x] Healthy state remains visually quiet; exceptional state receives stronger emphasis.
- [x] World begins directly below the global header without a duplicate page hero or shallow filter toolbar.

## 2. Structural model

- [x] Agents are the primary system units.
- [x] Assigned Knowledge, enabled Channels and aggregate conversation activity remain attributable to an Agent.
- [x] Conversation activity is aggregated; individual conversations are not rendered as World objects.
- [x] A Knowledge-only workspace renders coherently without Commerce controls or placeholders.
- [x] A Commerce-enabled workspace renders only server-authorized Catalog, collection and location scope.
- [x] Optional Commerce setup is explicit without presenting Commerce as a core requirement.

## 3. Navigation

- [x] World is the workspace home and is not duplicated as a navigation tab.
- [x] Inbox is directly reachable from the system header.
- [x] Other authorized focused workflows are reachable through the contextual launcher or World relationships.
- [x] Catalog, Locations and Collections launcher entries appear only when the capability exists.
- [x] Focused screens provide a clear return to the system and existing deep links remain compatible.

## 4. Responsive layout

- [x] One semantic DOM hierarchy is used at every viewport; there is no separate mobile renderer.
- [x] Agent units flow through CSS Grid without authored coordinates.
- [x] The number of Agent columns follows available width.
- [x] The optional business-data rail moves below the Agent field when horizontal space is insufficient.
- [x] The layout remains usable at 1440, 1024, 768, 390 and 320 pixels without horizontal page overflow.
- [x] No camera, pan, zoom, fit or projection controls are present.

## 5. Selection and inspector

- [x] Selecting or focusing an Agent emphasizes only its meaningful relationships without reordering the layout.
- [x] Selection opens an overlay DOM inspector and does not resize the World layout.
- [x] The inspector shows only relevant detail and routes configuration work to the owning focused screen.
- [x] Escape and the close control dismiss the inspector and return focus to the invoking control.
- [x] Keyboard focus remains within the modal inspector while it is open.

## 6. Visual grammar and state

- [x] Agent, Knowledge, Channel, Catalog, collection and location use stable distinguishable forms.
- [x] Agent representation does not use employee avatars, 3D perspective, rotate/flip effects or decorative game treatment.
- [x] Capability absence, empty data, degraded dependencies and authorization remain distinct states.
- [x] Essential state is communicated with text or semantics in addition to color.
- [x] Motion is limited to interaction/state feedback and respects `prefers-reduced-motion`.

## 7. Performance and accessibility

- [x] No layout simulation or continuous animation runs in the background.
- [x] World uses semantic HTML controls with visible focus treatment and accessible names.
- [x] The inspector is exposed as a labelled modal dialog and is keyboard operable.
- [x] Loading, empty, degraded and error states remain understandable to assistive technology.
- [x] The system remains understandable without opening the inspector first.

## 8. Anti-slop gate

- [x] Every visible object, relationship and metric has a clear product reason to exist.
- [x] No removable repeated metric or decorative-only panel remains.
- [x] No fabricated product, person, activity, provider-health or business data is shown.
- [x] World remains a read projection of authoritative server state.

Any unchecked applicable item fails the Phase 3.2.1 UI review.
