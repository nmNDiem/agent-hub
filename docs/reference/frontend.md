# Frontend architecture

## Boundaries

`apps/web` is the Next.js admin application. Route files stay thin and compose domain features; reusable UI belongs in shared components and API utilities. `apps/widget` is an independent TypeScript/Vite bundle and must not import the admin feature tree or credentials.

Use the generated/backend-owned API contract. Keep workspace, agent, channel and filter identity in query keys. Switching workspace cancels old requests and clears transient scoped state.

## Data and rendering

- Use Server Components for shell/non-interactive initial data where practical and client components for forms, tables, streams and charts.
- User-specific/authenticated requests use private/no-store semantics.
- Avoid duplicate fetching from mismatched server/client query keys.
- Do not fetch during render or store server state in unnecessary local/global state.
- Streaming updates are batched and retain partial output on cancel/failure.

## Errors and mutations

Map API failures once at the client boundary into safe feedback with `status`, `code` and `request_id`. Preserve form values on failure. A successful mutation followed by refresh failure remains a successful mutation with stale-view warning. Retry only idempotent or safely repeatable operations.

## Channel/inbox UI

- Connection status comes from the backend and distinguishes connected, action required, disconnected and provider error.
- Inbox lists use stable cursor pagination and URL-persisted filters.
- Sending shows persisted queued/sending/delivered/failed state; optimistic bubbles require reconciliation by message identity.
- AI/human mode, assignee and thread status are explicit controls with permission feedback.
- Never render raw provider HTML, private attachment URLs or unsanitized model markdown.

## Quality

TypeScript strict, established lint/test tooling, accessible primitives, responsive layout and explicit loading/empty/error/forbidden states. Do not add dependencies without a scoped reason.
