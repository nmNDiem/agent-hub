# Design system

## Direction

AgentHub is a premium, approachable SaaS control panel: neutral light surfaces, restrained emphasis, clear typography, compact but readable data density and real content imagery only where useful. The default admin palette is Lagoon; Aurora and Ember are allowlisted alternatives. The Website widget uses independent workspace branding.

## Tokens and layout

[`tokens.json`](tokens.json) is the machine-readable token source. Use semantic CSS variables/Tailwind mappings rather than one-off colors.

- Spacing follows 4 px increments; common values are 8, 12, 16, 24 and 32 px.
- Desktop sidebar is approximately 240-256 px; top bar 64 px; content max around 1600 px.
- Cards use approximately 12 px radius, controls 8-10 px and subtle borders/shadows.
- Page heading 30-32 px; section 18-20 px; body 14 px; metadata 12-13 px.
- `vi-VN` is the current UI language. Format currency and dates from actual locale/timezone data.

## Shared components

Use existing primitives and variants before creating new ones. Core patterns include AppShell, workspace switcher, Button/Input/Select/Dialog/Sheet/Tabs/Toast, StatusBadge, DataTable, MetricCard, ProductCard, ChatBubble, SourceChip, UploadDropzone, EmptyState and ConfirmDialog.

Every status has text in addition to color. IDs shown to users are canonical values with accessible copy behavior. Product cards never invent image, price, availability or options.

## Async states

Every async surface supports `loading | ready | empty | error | forbidden`; mutations add `submitting | success`, and delivery/streaming surfaces add appropriate queued/streaming/delivered/canceled/failed states. Preserve entered data and partial streamed content on recoverable failure.

Do not display navigation, metrics, notifications, channel connections or commercial upgrade prompts unless backed by real behavior and data.
