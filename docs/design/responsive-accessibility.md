# Responsive and accessibility

## Responsive behavior

Review at 1440, 1024, 768, 390 and 320 px. Desktop multi-pane workspaces become tabs or list-to-detail navigation below approximately 1024 px. Tables may become cards or bounded horizontal regions without hiding primary actions. Chat composers respect `dvh`, safe-area insets and on-screen keyboards.

## Keyboard and focus

- Provide a skip link and logical heading/order.
- All controls are keyboard reachable with visible focus.
- Escape closes modal/sheet/widget and restores focus to its trigger.
- Trap focus only in true modal/full-screen overlays.
- Primary mobile targets are at least 44 by 44 px.
- Streaming and list updates do not unexpectedly steal focus or scroll position.

## Semantics

- One page `h1`; labels and errors connected with `aria-describedby`.
- Icon-only buttons have accessible names.
- Status, assignment and delivery state include readable text.
- Streaming announcements are polite and throttled.
- Charts include a textual/table equivalent.
- Product imagery has meaningful alt text; decorative imagery is hidden.

## Localization and motion

Vietnamese diacritics and longer labels must not clip. Use locale-aware numbers, currency and timestamps. Meet WCAG contrast expectations, respect reduced motion and never rely on animation or color alone.
