# Responsive, accessibility and interaction quality

## Responsive matrix
| Width | Admin shell | Dashboard | Playground | Widget |
|---|---|---|---|---|
| >=1280 | expanded sidebar and topbar | 4 KPIs; 8/4 chart/list | persistent config/chat columns | floating 380–420 px panel |
| 1024–1279 | compact sidebar | 2×2 KPIs; chart/list may stack | 38/62 split if readable | floating panel capped to viewport |
| 768–1023 | collapsible Sheet nav | 2-column cards, stacked main | tabs, chat full width | floating panel |
| <768 | Sheet nav; compact topbar | 1-column cards and scrollable table alternative | tabs + fixed composer | full-screen or safe-area bottom sheet |

Viewport/touch: handle on-screen keyboard via `dvh`, safe-area insets, and sticky chat composer. Table on mobile may use list cards instead of horizontal scroll, preserving all important actions.

## Keyboard navigation
Skip-link; Tab order sidebar → topbar → main; Escape closes menu/dialog/widget and returns focus; Enter/Space toggles launcher; list arrow keys only where ARIA semantics require; upload button accessible without drag/drop. Do not trap focus in normal chat pane; trap only modal/full-screen widget when appropriate.

## Semantics and announcements
Heading hierarchy single `h1`; charts offer text or tabular equivalent; icon-only actions have `aria-label`; status includes word labels; streaming replies announced politely with throttled updates to avoid screen-reader spam; validation text linked via `aria-describedby`; image cards have meaningful product alt text; decorations `aria-hidden`.

## Contrast, sizing, localization
Text contrast >=4.5:1 where required; large text >=3:1; visible focus; minimum mobile targets 44×44 px for key actions. Never rely only on green/red badges; `vi-VN` numeral, currency and dates; Vietnamese length expansion tested, avoid hardcoded widths for label text. Respect `prefers-reduced-motion` and `prefers-contrast` where feasible.

## Performance feel
Do not block shell on dashboard analytics; defer charts and image thumbnails, image lazy loading, preserve chat scroll position when history loads, scroll to bottom only if user is already near bottom. Streaming UI batches updates; avoid replaying full conversation after every token.
