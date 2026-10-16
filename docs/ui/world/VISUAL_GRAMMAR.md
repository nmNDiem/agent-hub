# AgentHub World — Visual Grammar

## 1. Principle

Visual form is semantic. Every recurring shape, line, label and motion must have a stable meaning.

Do not invent visual differences merely to make the canvas look rich.

> One visual form = one recurring domain meaning.

---

## 2. Object classes

### 2.1 Agent — primary core

Role:

- central processing / orchestration object
- primary anchor of a workspace cluster

Visual character:

- strongest object in its cluster
- circular or compact core form
- clear label
- state ring or concise status treatment

Do not use:

- employee avatars
- character illustrations
- 3D robot mascots
- oversized decorative badges

The object may use an abstract system/agent glyph.

### 2.2 Knowledge — intelligence source

Role:

- source of knowledge assigned to an agent

Visual character:

- smaller than agent
- source/memory/document-derived form
- may aggregate multiple sources at lower zoom

At Level B:

```text
Knowledge
3 sources
```

At Level C it may decompose into named knowledge bases or sources.

Do not show chunk count by default unless the current task needs it.

### 2.3 Channel — external gateway

Role:

- entry/exit boundary between AgentHub and an external messaging surface

Visual character:

- gateway/port object
- placed toward outer boundary of the agent cluster
- edge direction should make inbound/outbound relationship understandable

Examples:

- Website
- Facebook
- Zalo

Provider logos are allowed as identifiers, but the UI should not become a logo wall.

### 2.4 Catalog scope — business scope hub

Role:

- represents the catalog domain accessible to an agent

Visual character:

- grouped structural object
- visually distinct from agent and knowledge
- may unfold into collections and locations at higher zoom

Do not render every product as a node.

### 2.5 Collection — catalog grouping

Role:

- product grouping inside catalog scope

Visual character:

- child of catalog scope
- lower visual weight than catalog scope

Only show counts when that count is useful in the current projection.

### 2.6 Location — operational endpoint

Role:

- store / warehouse / stock location

Visual character:

- terminal or endpoint in catalog structure
- stable location symbol

A location node should not simultaneously display price, stock, SKU, warning state and product count. Detail belongs in focus/inspector.

### 2.7 Customer / conversation activity — aggregate population

Role:

- runtime activity, not static structure

Visual character:

- compact aggregate
- population cloud, restrained particles or flow
- visually secondary to structural nodes

Do not render one permanent dot per actual contact or conversation at scale.

### 2.8 Human handoff — handling state

Role:

- indicates conversation ownership/handling transition

Visual character:

- state or branch off runtime activity
- not a top-level permanent domain node unless later product behavior requires it

---

## 3. Edge grammar

Edges must carry meaning.

### Structural edge

Meaning:

- configured relationship

Examples:

```text
Knowledge -> Agent
Agent -> Catalog scope
```

Treatment:

- quiet by default
- stronger when selected/focused
- no constant glowing animation

### Channel flow edge

Meaning:

- connection to message channel

Treatment:

- may support restrained directional activity
- should not imply current message volume unless a traffic projection explicitly encodes it

### Runtime flow

Meaning:

- current activity

Treatment:

- subtle particles or pulse
- aggregation first
- may stop entirely when reduced-motion is enabled

### Error/attention edge

Meaning:

- a relationship is degraded or blocked

Treatment:

- emphasize only the affected segment
- attach concise reason to the affected object

---

## 4. Labels

Labels are part of hierarchy, not decoration.

### Always eligible at normal zoom

- selected/focused object name
- agent names
- major domain group labels when needed for orientation

### Conditional

- counts
- secondary metadata
- provider state
- source count
- location detail

### Hidden at lower zoom

- long descriptions
- record metadata
- timestamps
- IDs
- raw statuses

Use progressive disclosure rather than truncating dozens of labels into visual noise.

---

## 5. Status grammar

Keep state vocabulary small.

Recommended semantic states:

```text
normal
active
processing
attention
error
paused
disabled
```

Do not invent separate colors for every backend enum.

Backend states should map into this visual vocabulary.

Healthy objects do not need repeated `Healthy` text labels.

---

## 6. Color rules

Color has semantic priority:

1. current selection/focus
2. exceptional state
3. domain differentiation
4. decorative ambience

Never reverse this order.

Dark mode is appropriate for the spatial canvas, but readability must not depend on bloom/glow.

Avoid:

- rainbow graph colors
- unique color for every node
- strong neon on every edge
- gradients that do not encode meaning

---

## 7. Depth rules

The World is 2D.

Allowed:

- scale hierarchy
- blur for distant/secondary ambience
- subtle shadow
- opacity hierarchy
- overlap management

Not allowed:

- perspective camera
- card tilt
- 3D rotation
- flip transitions
- faux-isometric UI
- objects floating at arbitrary Z-depth for decoration

---

## 8. Motion grammar

Motion must communicate one of:

- activity
- transition of focus
- topology change
- state change
- causal relationship

If motion communicates none of those, remove it.

Examples of valid motion:

- camera smoothly focuses selected agent
- newly connected channel edge appears and settles
- subtle message particle travels toward agent in activity mode
- knowledge ingestion state changes from processing to ready

Invalid motion:

- perpetual breathing on every node
- random floating
- rotating icons
- flipping cards
- continuous edge shimmer everywhere

---

## 9. Density rule

A cluster should remain understandable before it becomes impressive.

When density rises, use this order:

1. hide secondary labels
2. aggregate child records
3. collapse substructure
4. simplify edges
5. introduce focus/filter

Do not solve density by shrinking everything.
