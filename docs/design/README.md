# Design documentation

## Reference images and precedence
1. `../../assets/reference/01-admin-dashboard.png`: overarching admin visual language.
2. `../../assets/reference/02-chatbot-playground.png`: assistant setup + test surface.
3. `../../assets/reference/03-website-chat-widget.png`: shop-facing embeddable widget.

Precedence on conflicts: **product decisions → documented UX/behaviour/accessibility → design tokens/components → screenshots**. AI-generated examples contain fictional data and may contain misplaced elements or mislabeled menu entries. Design decisions can be updated deliberately; do not turn them into random one-off CSS overrides.

## Main documents
- `design-system.md` and `tokens.json` — tokens, typography, spacing, layouts, themes and visual criteria.
- `component-spec.md` — shared components, interactions and semantic behaviour.
- `navigation-and-ia.md` — route map, nav, shop switching, permissions and empty modules.
- `screens/dashboard.md`, `screens/playground.md`, `screens/widget.md`, `screens/conversations.md`, `screens/chatbots.md`, `screens/catalog-and-knowledge.md`, `screens/auth-and-onboarding.md` — screen-level specs.
- `flows-and-states.md` — journeys, state machines and edge cases.
- `responsive-accessibility.md` — responsive sizing, a11y and motion.
- `reference-assets.md` — reference image handoff/what not to implement from images.
- `qa.md` — checklists with verifiable acceptance conditions.

## Design language
The design direction is a premium, approachable SaaS control panel. Use a neutral/light foundation, restrained blue emphasis, clear text, subtle hairlines, tasteful surfaces and fashion imagery only where it adds content. The admin UI is **not** a luxury storefront; per-shop widget branding is independently configurable. The default interface is Vietnamese (`vi-VN`) with architecture prepared for `en`; reference images happen to show English and are not a language requirement.
