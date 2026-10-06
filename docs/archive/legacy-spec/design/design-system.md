# Design system v1

## Visual hierarchy
- Default light mode with Lagoon as the initial admin palette. Aurora and Ember are user-selectable alternatives persisted in browser storage; dark mode remains deferred and no incomplete dark-mode control is shown.
- Three planes: page canvas, elevated card, interactive surface. One primary action per section. Deep navy text, palette-driven action/highlight colors and neutral grays; green/amber/red remain reserved for meaningful status where they are not the active brand color.
- Font: `Inter` (or `Geist Sans` with a single consistent font choice) for UI, monospace only for technical identifiers. Vietnamese diacritics must render cleanly. Do not use screenshot product photography as a font or encode labels into an image.

## Authoritative starter CSS tokens
Use semantic tokens (Tailwind CSS variables and shadcn/ui color mapping), not arbitrary hex per component. Values below are design starting points; check actual contrast and adapt global tokens if necessary.

```css
:root {
  --background: 180 30% 98%; --foreground: 222 47% 11%;
  --card: 0 0% 100%; --card-foreground: 222 47% 11%;
  --popover: 0 0% 100%; --popover-foreground: 222 47% 11%;
  --primary: 174 76% 25%; --primary-foreground: 0 0% 100%;
  --secondary: 214 32% 95%; --secondary-foreground: 222 47% 18%;
  --muted: 210 30% 96%; --muted-foreground: 215 16% 39%;
  --accent: 174 67% 94%; --accent-foreground: 174 76% 25%;
  --destructive: 0 74% 45%; --destructive-foreground: 0 0% 100%;
  --border: 214 25% 89%; --input: 214 25% 89%; --ring: 174 76% 25%;
  --radius: 0.75rem;
}
.dark { /* define complete equivalent semantic values; do not invert photos/charts */ }
```

## Spacing and geometry
- Base spacing: 4 px increments; frequent values 8/12/16/24/32; card gap 16–24.
- Sidebar 240–256 px desktop; collapsed 64–72 px. Topbar 64 px. Content max ~1600 px, padding 24–32 desktop / 16 tablet / 12–16 mobile.
- Card radius 12 px; buttons/inputs 8–10 px; pills full-round. Borders 1 px; subtle shadow on modal/floating widget, not all cards.
- Desktop dashboard: 12-column grid; four KPI cards at >=1280 px, 2×2 at tablet, 1–2 at phone. Main chart spans ~8/12, right list ~4/12; at narrow widths stack.
- Copy/metrics must wrap/truncate thoughtfully, not overflow. A copied identifier shows monospace, end ellipsis and copy button; underlying copied value is the canonical unprefixed UUIDv7.

## Typography and density
| Use | Size / line-height | Weight |
|---|---|---|
| Main page heading | 30–32 / 38 | 650–700 |
| Section heading | 18–20 / 28 | 600–650 |
| Card title | 15–16 / 24 | 600 |
| Body | 14 / 21 | 400–500 |
| Table/meta | 12–13 / 18 | 400–500 |
| KPI | 28–32 / 36 | 650–700 |

Use Vietnamese labels in actual MVP; format VND with `Intl.NumberFormat('vi-VN', {style:'currency',currency:'VND'})`, dates based on viewer locale and timezone, not fixed dates from images.

## Components and libraries
Next.js App Router + TypeScript; Tailwind + shadcn/ui + Radix primitives, Lucide icons; React Hook Form + Zod, TanStack Query/Table, Recharts, next-themes. Avoid introducing global state unless needed; TanStack Query for server state, URL params for filters, local state for transient widget/modal UI. Build `Button`, `Input`, `Select`, `Dialog`, `Sheet`, `Tabs`, `Toast`, `Skeleton`, `EmptyState`, `StatusBadge`, `CopyId`, `MetricCard`, `DataTable`, `ProductCard`, `ChatBubble`, `SourceChip`, `UploadDropzone`, `WidgetPreview` as reusable variants.

## Brand boundaries
The admin shell uses semantic palette tokens with Lagoon as the default and Aurora/Ember as alternatives. Only allowlisted palette identifiers may reach the root `data-palette` attribute. The embedded widget's `brand_color`, launcher icon, greeting, name and logo remain independent published bot settings; use scoped CSS/shadow root to avoid host CSS collisions, with no admin-specific navigation inside the widget. Never hotlink the AI-generated mockup as the shop's real product imagery.

## Motion and focus
150–220 ms transitions for hover/sheet; disable unnecessary animation with `prefers-reduced-motion`. Focus ring visible for all buttons and inputs, 44×44 px target for mobile primary actions. All color-coded statuses also have readable text/icons. Loading avoids layout jumps by reserving dimensions.
